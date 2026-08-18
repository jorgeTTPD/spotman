from collections import Counter

from rich.markup import escape
from textual import on
from textual.binding import Binding
from textual.containers import Horizontal
from textual.screen import Screen
from textual.widgets import Button, RadioSet, Static

from ..widgets import (
    ConfirmScreen,
    ListPickerModal,
    PlaylistPicker,
    bordered_container,
)


class CleanupScreen(Screen):
    

    BINDINGS = [
        Binding("q", "back", "Volver"),
        Binding("z", "undo", "Deshacer", show=False),
    ]

    CSS = """
    CleanupScreen {
        align: center middle;
        padding: 1;
    }
    #cleanup-box {
        width: 84;
        height: auto;
        padding: 1 2;
    }
    #types {
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

    TYPES = [
        ("dups", "Duplicados (mantener la 1ª)"),
        ("unavailable", "No disponibles (locales / no reproducibles)"),
        ("podcasts", "Podcasts / episodios"),
        ("artist", "Canciones de un artista"),
        ("album", "Canciones de un álbum"),
    ]

    def __init__(self):
        super().__init__()
        self._type = None
        self._playlist = None
        self._tracks = []
        self._target_uris = []
        self._undo = []
        self._processing = False

    def action_back(self):
        self.app.pop_screen()

    def compose(self):
        with bordered_container(title="🧹 Limpieza avanzada", id="cleanup-box"):
            yield Static("¿Qué quieres limpiar?", id="prompt")
            yield RadioSet(
                *(label for _, label in self.TYPES),
                id="types",
            )
            with Horizontal(id="go"):
                yield Button("Continuar", id="go-btn", variant="primary")
            yield Static("Elige un tipo y pulsa Continuar.", id="status", markup=True)

    def on_mount(self):
        self.query_one("#types", RadioSet).focus()

    @on(RadioSet.Changed, "#types")
    def on_type_changed(self, event):
        index = event.radio_set.pressed_index
        if index is not None and 0 <= index < len(self.TYPES):
            self._type = self.TYPES[index][0]

    def on_button_pressed(self, event):
        if event.button.id == "go-btn":
            self._start()

    def _start(self):
        if self._processing:
            return
        if not self._type:
            self.app.notify("Elige un tipo de limpieza", severity="warning")
            return
        self.app.push_screen(
            PlaylistPicker(self.app.client, title="Elige playlist"),
            callback=self._on_picked,
        )

    def _on_picked(self, playlist):
        if not self.is_mounted:
            return
        if playlist is None:
            return
        self._playlist = playlist
        self.query_one("#status", Static).update(
            f"Analizando '{escape(playlist.get('name', '?'))}'..."
        )
        self._analyze()

    def _analyze(self):
        def load():
            tracks = self.app.client.get_playlist_tracks(self._playlist["id"]) or []
            self.app.call_from_thread(self._analyzed, tracks)

        self.run_worker(load, thread=True)

    def _analyzed(self, tracks):
        if not self.is_mounted:
            return
        self._tracks = tracks
        if self._type in ("artist", "album"):
            self._pick_target()
            return
        self._show_confirm(*self._compute_uris(tracks))

    def _counts(self):
        counter = Counter()
        for t in self._tracks:
            if self._type == "artist":
                for name in t.get("artists_list") or []:
                    if name:
                        counter[name] += 1
            else:
                album = t.get("album")
                if album:
                    counter[album] += 1
        return counter

    def _pick_target(self):
        counts = self._counts()
        if not counts:
            self.query_one("#status", Static).update(
                "[green]✓ No hay artistas/álbumes en esta playlist.[/green]"
            )
            return
        title = "Elige artista" if self._type == "artist" else "Elige álbum"
        rows = [(name, str(count)) for name, count in counts.most_common()]
        self.app.push_screen(
            ListPickerModal(title=title, rows=rows),
            callback=self._on_target,
        )

    def _on_target(self, target):
        if not self.is_mounted or target is None:
            return
        if self._type == "artist":
            uris = [
                t["uri"]
                for t in self._tracks
                if t.get("uri") and target in (t.get("artists_list") or [])
            ]
        else:
            uris = [
                t["uri"]
                for t in self._tracks
                if t.get("uri") and t.get("album") == target
            ]
        label = f"{len(uris)} canciones de '{escape(target)}'"
        self._show_confirm(uris, label)

    def _compute_uris(self, tracks):
        if self._type == "dups":
            seen = set()
            dup_uris = []
            for t in tracks:
                uri = t.get("uri", "")
                if not uri:
                    continue
                if uri in seen:
                    dup_uris.append(uri)
                else:
                    seen.add(uri)
            return dup_uris, f"{len(dup_uris)} duplicados"
        if self._type == "unavailable":
            uris = [
                t["uri"]
                for t in tracks
                if t.get("uri")
                and (t.get("is_local") or t.get("is_playable") is False)
            ]
            return uris, f"{len(uris)} canciones no disponibles"
        if self._type == "podcasts":
            uris = [
                t["uri"]
                for t in tracks
                if t.get("uri")
                and (
                    t.get("type") == "episode"
                    or str(t.get("uri", "")).startswith("spotify:episode:")
                )
            ]
            return uris, f"{len(uris)} podcasts"
        return [], "nada"

    def _show_confirm(self, uris, label):
        self._target_uris = uris
        if not uris:
            self.query_one("#status", Static).update(
                "[green]✓ No hay nada que limpiar.[/green]"
            )
            return
        pl = escape(self._playlist.get("name", "?"))
        self.app.push_screen(
            ConfirmScreen(
                "⚠️ Confirmar limpieza",
                f"Se eliminarán [bold]{len(uris)}[/bold] canciones ({label}) "
                f"de '{pl}'.\\n\\n[red]Esta acción no se puede deshacer desde Spotify.[/red]",
                confirm_label="Sí, eliminar",
            ),
            callback=self._on_confirm,
        )

    def _on_confirm(self, confirmed):
        if not self.is_mounted or not confirmed:
            return
        self._processing = True
        self.query_one("#status", Static).update("Eliminando...")
        pl = self._playlist
        uris = list(self._target_uris)

        def load():
            ok = self.app.client.remove_tracks(pl["id"], uris)
            self.app.call_from_thread(self._done, ok, pl, uris)

        self.run_worker(load, thread=True)

    def _done(self, ok, pl, uris):
        if not self.is_mounted:
            return
        self._processing = False
        if ok:
            self._undo.append((pl["id"], uris))
            if len(self._undo) > 20:
                self._undo.pop(0)
            self.query_one("#status", Static).update(
                f"[green]✓ {len(uris)} canciones eliminadas.[/green]\\n"
                "[dim]Pulsa z para deshacer.[/dim]"
            )
            self.app.notify(f"{len(uris)} canciones eliminadas")
        else:
            self.query_one("#status", Static).update(
                "[red]✗ Error al eliminar. Re-autentícate (nuevos permisos requeridos).[/red]"
            )

    def action_undo(self):
        if self._processing or not self._undo:
            self.app.notify("Nada que deshacer", severity="warning")
            return
        pl_id, uris = self._undo.pop()
        self._processing = True
        self.query_one("#status", Static).update("Deshaciendo...")

        def load():
            ok = self.app.client.add_tracks(pl_id, uris)
            self.app.call_from_thread(self._undone, ok, len(uris))

        self.run_worker(load, thread=True)

    def _undone(self, ok, count):
        if not self.is_mounted:
            return
        self._processing = False
        if ok:
            self.query_one("#status", Static).update(
                f"[green]✓ Deshecho: {count} canciones restauradas.[/green]"
            )
            self.app.notify(f"{count} canciones restauradas")
        else:
            self.query_one("#status", Static).update(
                "[red]✗ Error al deshacer. Re-autentícate (nuevos permisos requeridos).[/red]"
            )
