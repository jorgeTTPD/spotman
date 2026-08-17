from collections import defaultdict

from rich.markup import escape
from textual import on
from textual.binding import Binding
from textual.containers import Horizontal
from textual.screen import Screen
from textual.widgets import Button, RadioSet, Static

from ..widgets import (
    ConfirmScreen,
    MultiPlaylistPicker,
    PlaylistPicker,
    TextInputModal,
    bordered_container,
)


class MergeScreen(Screen):
    """Fusionar playlists y dividir por artista/álbum."""

    BINDINGS = [
        Binding("q", "back", "Volver"),
        Binding("z", "undo", "Deshacer", show=False),
    ]

    CSS = """
    MergeScreen {
        align: center middle;
        padding: 1;
    }
    #merge-box {
        width: 84;
        height: auto;
        padding: 1 2;
    }
    #modes {
        margin-top: 1;
        margin-bottom: 1;
    }
    #go {
        align-horizontal: center;
        margin-bottom: 1;
    }
    #status {
        height: auto;
        max-height: 60%;
        overflow-y: auto;
    }
    """

    MODES = [
        ("merge", "Fusionar playlists"),
        ("merge_dedupe", "Fusionar sin duplicados"),
        ("split_artist", "Dividir por artista"),
        ("split_album", "Dividir por álbum"),
    ]

    def __init__(self):
        super().__init__()
        self._mode = None
        self._sources = []
        self._source = None
        self._groups = []
        self._undo = []
        self._processing = False

    def action_back(self):
        self.app.pop_screen()

    def compose(self):
        with bordered_container(title="🔀 Fusionar / Dividir playlists", id="merge-box"):
            yield Static("¿Qué quieres hacer?", id="prompt")
            yield RadioSet(
                *(label for _, label in self.MODES),
                id="modes",
            )
            with Horizontal(id="go"):
                yield Button("Continuar", id="go-btn", variant="primary")
            yield Static("Elige una operación y pulsa Continuar.", id="status", markup=True)

    def on_mount(self):
        self.query_one("#modes", RadioSet).focus()

    @on(RadioSet.Changed, "#modes")
    def on_mode_changed(self, event):
        index = event.radio_set.pressed_index
        if index is not None and 0 <= index < len(self.MODES):
            self._mode = self.MODES[index][0]

    def on_button_pressed(self, event):
        if event.button.id == "go-btn":
            self._start()

    def _start(self):
        if self._processing:
            return
        if not self._mode:
            self.app.notify("Elige una operación", severity="warning")
            return
        if self._mode in ("merge", "merge_dedupe"):
            self.app.push_screen(
                MultiPlaylistPicker(self.app.client, title="Elige playlists"),
                callback=self._on_sources,
            )
        else:
            self.app.push_screen(
                PlaylistPicker(self.app.client, title="Elige playlist a dividir"),
                callback=self._on_source,
            )





    def _on_sources(self, sources):
        if not self.is_mounted:
            return
        if not sources:

            return
        self._sources = sources
        default = f"Fusión de {len(sources)} playlists"
        self.app.push_screen(
            TextInputModal(
                "🔀 Fusionar",
                "Nombre de la playlist resultante:",
                default=default,
                confirm_label="Fusionar",
            ),
            callback=self._on_merge_name,
        )

    def _on_merge_name(self, name):
        if not self.is_mounted or not name:
            return
        self._processing = True
        self.query_one("#status", Static).update("Fusionando...")
        sources = list(self._sources)
        dedupe = self._mode == "merge_dedupe"

        def load():
            all_uris = []
            seen = set()
            for pl in sources:
                tracks = self.app.client.get_playlist_tracks(pl["id"]) or []
                for t in tracks:
                    uri = t.get("uri", "")
                    if not uri:
                        continue
                    if dedupe:
                        if uri in seen:
                            continue
                        seen.add(uri)
                    all_uris.append(uri)
            if not all_uris:
                self.app.call_from_thread(self._merged_empty)
                return
            new_id = self.app.client.create_playlist(name, public=False)
            ok = False
            if new_id:
                ok = self.app.client.add_tracks(new_id, all_uris)
                if not ok:

                    self.app.client.delete_playlist(new_id)
            self.app.call_from_thread(self._merged, ok, new_id, name, len(all_uris))

        self.run_worker(load, thread=True)

    def _merged_empty(self):
        if not self.is_mounted:
            return
        self._processing = False
        self.query_one("#status", Static).update(
            "[yellow]⚠️ Las playlists seleccionadas no tienen canciones; no se creó nada.[/yellow]"
        )

    def _merged(self, ok, new_id, name, count):
        if not self.is_mounted:
            return
        self._processing = False
        if ok and new_id:
            self._undo.append({"op": "merge", "ids": [new_id]})
            self._trim_undo()
            self.query_one("#status", Static).update(
                f"[green]✓ Playlist '{escape(name)}' creada con {count} canciones.[/green]\n"
                "[dim]Pulsa z para deshacer.[/dim]"
            )
            self.app.notify(f"Fusión creada con {count} canciones")
        else:
            self.query_one("#status", Static).update(
                "[red]✗ Error al fusionar. Re-autentícate (nuevos permisos requeridos).[/red]"
            )





    def _on_source(self, playlist):
        if not self.is_mounted:
            return
        if playlist is None:
            return
        self._source = playlist
        self.query_one("#status", Static).update(
            f"Analizando '{escape(playlist.get('name', '?'))}'..."
        )

        def load():
            tracks = self.app.client.get_playlist_tracks(playlist["id"]) or []
            self.app.call_from_thread(self._analyzed, tracks)

        self.run_worker(load, thread=True)

    def _analyzed(self, tracks):
        if not self.is_mounted:
            return
        by_key = defaultdict(list)
        for t in tracks:
            uri = t.get("uri", "")
            if not uri:
                continue
            if self._mode == "split_artist":
                key = (t.get("artists_list") or [t.get("artist", "?")])[0]
                key = key or "Desconocido"
            else:
                key = t.get("album") or "Desconocido"
            by_key[key].append(uri)
        self._groups = sorted(by_key.items(), key=lambda kv: -len(kv[1]))
        if not self._groups:
            self.query_one("#status", Static).update(
                "[green]✓ No hay canciones para dividir.[/green]"
            )
            return
        lines = [f"Se crearán {len(self._groups)} playlists:", ""]
        for name, uris in self._groups[:12]:
            lines.append(f"  • {escape(name)} ({len(uris)})")
        if len(self._groups) > 12:
            lines.append(f"  • ... y {len(self._groups) - 12} más")
        self.app.push_screen(
            ConfirmScreen(
                "🔀 Dividir playlist",
                "\n".join(lines),
                confirm_label="Dividir",
            ),
            callback=self._on_split_confirm,
        )

    def _on_split_confirm(self, confirmed):
        if not self.is_mounted or not confirmed:
            return
        self._processing = True
        self.query_one("#status", Static).update("Dividiendo...")
        groups = list(self._groups)

        def load():
            created = []
            for name, uris in groups:
                new_id = self.app.client.create_playlist(name, public=False)
                if new_id:
                    ok = self.app.client.add_tracks(new_id, uris)
                    if ok:
                        created.append(new_id)
            self.app.call_from_thread(self._split_done, created)

        self.run_worker(load, thread=True)

    def _split_done(self, created):
        if not self.is_mounted:
            return
        self._processing = False
        if created:
            self._undo.append({"op": "split", "ids": created})
            self._trim_undo()
            self.query_one("#status", Static).update(
                f"[green]✓ {len(created)}/{len(self._groups)} playlists creadas.[/green]\n"
                "[dim]Pulsa z para deshacer.[/dim]"
            )
            self.app.notify(f"{len(created)} playlists creadas")
        else:
            self.query_one("#status", Static).update(
                "[red]✗ Error al dividir. Re-autentícate (nuevos permisos requeridos).[/red]"
            )





    def action_undo(self):
        if self._processing or not self._undo:
            self.app.notify("Nada que deshacer", severity="warning")
            return
        entry = self._undo.pop()
        self._processing = True
        self.query_one("#status", Static).update("Deshaciendo...")

        def load():
            ok = all(self.app.client.delete_playlist(pid) for pid in entry["ids"])
            self.app.call_from_thread(self._undone, ok, len(entry["ids"]))

        self.run_worker(load, thread=True)

    def _undone(self, ok, count):
        if not self.is_mounted:
            return
        self._processing = False
        if ok:
            self.query_one("#status", Static).update(
                f"[green]✓ Deshecho: {count} playlists eliminadas.[/green]"
            )
            self.app.notify(f"{count} playlists eliminadas")
        else:
            self.query_one("#status", Static).update(
                "[red]✗ Error al deshacer. Re-autentícate (nuevos permisos requeridos).[/red]"
            )

    def _trim_undo(self):
        if len(self._undo) > 20:
            self._undo.pop(0)
