from rich.markup import escape
from textual import on
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import Button, DataTable, Static

from ..widgets import ConfirmScreen, PlaylistPicker, bordered_container


class MoveScreen(Screen):
    """Mover canciones: selecciona en la playlist origen y muévelas a otra (con deshacer z)."""

    BINDINGS = [
        Binding("q", "back", "Volver"),
        Binding("space", "toggle_select", "Marcar", show=False),
        Binding("a", "select_all", "Todo", show=False),
        Binding("d", "deselect_all", "Nada", show=False),
        Binding("i", "invert_selection", "Invertir", show=False),
        Binding("m", "move_selected", "Mover", show=False),
        Binding("z", "undo", "Deshacer", show=False),
    ]

    CSS = """
    MoveScreen {
        height: 100%;
        padding: 1;
    }
    #wrap {
        height: 100%;
    }
    #tracks-box {
        height: 1fr;
    }
    #status {
        height: auto;
        margin-top: 1;
        padding: 0 1;
    }
    #actions {
        height: auto;
        margin-top: 1;
        align-horizontal: center;
    }
    """

    def __init__(self):
        super().__init__()
        self._source = None      # playlist origen
        self._tracks = []
        self._row_keys = {}
        self._marker_col = None
        self._selected = set()
        self._undo = []          # pila de (origen, destino, uris)
        self._processing = False

    def action_back(self):
        self.app.pop_screen()

    def compose(self):
        with Vertical(id="wrap"):
            with bordered_container(title="Canciones (origen)", id="tracks-box"):
                yield DataTable(
                    id="tracks-table", cursor_type="row", zebra_stripes=True
                )
            yield Static(
                "Elige la playlist origen, marca canciones y muévelas (m).",
                id="status",
                markup=True,
            )
            with Horizontal(id="actions"):
                yield Button("Elegir origen...", id="pick-src", variant="primary")
                yield Button("Mover a otra playlist", id="move-btn")

    def on_mount(self):
        self.query_one("#tracks-table", DataTable).focus()
        self._pick_source()

    def _pick_source(self):
        self.app.push_screen(
            PlaylistPicker(self.app.client, title="Elige playlist origen"),
            callback=self._on_source,
        )

    @on(Button.Pressed, "#pick-src")
    def on_pick_src(self):
        self._pick_source()

    def _on_source(self, playlist):
        if not self.is_mounted:
            return
        if playlist is None:
            return
        self._source = playlist
        self.query_one("#tracks-box").border_title = (
            f"{playlist.get('name', '?')} — canciones"
        )
        self.query_one("#status", Static).update(
            f"Cargando '{escape(playlist.get('name', '?'))}'..."
        )
        self._load_tracks()

    def _load_tracks(self):
        self._processing = True

        def load():
            tracks = self.app.client.get_playlist_tracks(self._source["id"]) or []
            self.app.call_from_thread(self._populated, tracks)

        self.run_worker(load, thread=True)

    def _populated(self, tracks):
        if not self.is_mounted:
            return
        self._processing = False
        self._tracks = tracks
        self._selected = set()
        self._row_keys = {}
        table = self.query_one("#tracks-table", DataTable)
        table.clear(columns=True)
        self._marker_col = table.add_column("✓")
        table.add_column("Artista")
        table.add_column("Título")
        table.add_column("Álbum")
        for i, t in enumerate(self._tracks):
            rk = table.add_row(
                "",
                t.get("artist", ""),
                t.get("name", ""),
                t.get("album", ""),
            )
            self._row_keys[i] = rk
        self._update_status()

    # ------------------------------------------------------------------
    # Selección
    # ------------------------------------------------------------------

    def _tracks_focused(self):
        try:
            return self.app.focused is self.query_one("#tracks-table", DataTable)
        except Exception:
            return False

    def _set_marker(self, index, selected):
        table = self.query_one("#tracks-table", DataTable)
        rk = self._row_keys.get(index)
        if rk is None or self._marker_col is None:
            return
        table.update_cell(rk, self._marker_col, "✓" if selected else "", update_width=False)

    def _toggle_index(self, index):
        t = self._tracks[index]
        self._set_selected(index, t, t.get("uri") not in self._selected)

    def _apply_selection(self, func):
        if self._processing or not self._tracks or not self._tracks_focused():
            return
        for i, t in enumerate(self._tracks):
            func(i, t)
        self._update_status()

    def _set_selected(self, i, t, on):
        if not t.get("uri"):
            return
        if on:
            self._selected.add(t["uri"])
            self._set_marker(i, True)
        else:
            self._selected.discard(t["uri"])
            self._set_marker(i, False)

    def action_toggle_select(self):
        if self._processing or not self._tracks or not self._tracks_focused():
            return
        table = self.query_one("#tracks-table", DataTable)
        index = table.cursor_row
        if index is None or not (0 <= index < len(self._tracks)):
            return
        self._toggle_index(index)
        self._update_status()

    def action_select_all(self):
        self._apply_selection(lambda i, t: self._set_selected(i, t, True))

    def action_deselect_all(self):
        self._apply_selection(lambda i, t: self._set_selected(i, t, False))

    def action_invert_selection(self):
        def flip(i, t):
            self._set_selected(i, t, t.get("uri") not in self._selected)

        self._apply_selection(flip)

    def _selected_uris(self):
        return [t["uri"] for t in self._tracks if t.get("uri") in self._selected]

    def _update_status(self):
        status = self.query_one("#status", Static)
        if not self._source:
            status.update("Elige la playlist origen para empezar.")
            return
        sel = len(self._selected)
        status.update(
            f"[bold]{escape(self._source.get('name', '?'))}[/bold] — "
            f"{len(self._tracks)} tracks | [cyan]{sel} seleccionadas[/cyan]\n"
            "[dim]espacio marcar · a todo · d nada · i invertir · "
            "m mover · z deshacer[/dim]"
        )

    # ------------------------------------------------------------------
    # Mover
    # ------------------------------------------------------------------

    @on(Button.Pressed, "#move-btn")
    def on_move_btn(self):
        self._confirm_move()

    def action_move_selected(self):
        if not self._tracks_focused():
            return
        self._confirm_move()

    def _confirm_move(self):
        if self._processing or not self._source:
            return
        uris = self._selected_uris()
        if not uris:
            self.app.notify("No hay canciones seleccionadas", severity="warning")
            return
        self.app.push_screen(
            PlaylistPicker(self.app.client, title="Elige playlist destino"),
            callback=lambda target: self._on_target(target, uris),
        )

    def _on_target(self, target, uris):
        if not self.is_mounted or target is None:
            return
        if target.get("id") == self._source["id"]:
            self.app.notify("No puedes mover a la misma playlist", severity="warning")
            return
        self.app.push_screen(
            ConfirmScreen(
                "🚚 Mover canciones",
                f"¿Mover {len(uris)} canciones de "
                f"'{escape(self._source.get('name', '?'))}' a "
                f"'{escape(target.get('name', '?'))}'?",
                confirm_label="Mover",
            ),
            callback=lambda ok: self._do_move(ok, target, uris),
        )

    def _do_move(self, ok, target, uris):
        if not self.is_mounted or not ok:
            return
        self._processing = True
        self.query_one("#status", Static).update("Moviendo...")
        src = self._source

        def load():
            added = self.app.client.add_tracks(target["id"], uris)
            removed = self.app.client.remove_tracks(src["id"], uris) if added else False
            self.app.call_from_thread(self._moved, added and removed, src, target, uris)

        self.run_worker(load, thread=True)

    def _moved(self, ok, src, target, uris):
        if not self.is_mounted:
            return
        self._processing = False
        if ok:
            self._undo.append((src["id"], target["id"], uris))
            if len(self._undo) > 20:
                self._undo.pop(0)
            self.app.notify(f"{len(uris)} canciones movidas")
            self._load_tracks()
        else:
            self.query_one("#status", Static).update(
                "[red]✗ Error al mover. Re-autentícate (nuevos permisos requeridos).[/red]"
            )

    # ------------------------------------------------------------------
    # Deshacer
    # ------------------------------------------------------------------

    def action_undo(self):
        if self._processing or not self._undo:
            self.app.notify("Nada que deshacer", severity="warning")
            return
        src_id, target_id, uris = self._undo.pop()
        self._processing = True
        self.query_one("#status", Static).update("Deshaciendo...")

        def load():
            removed = self.app.client.remove_tracks(target_id, uris)
            ok = removed and self.app.client.add_tracks(src_id, uris)
            self.app.call_from_thread(self._undone, ok, len(uris))

        self.run_worker(load, thread=True)

    def _undone(self, ok, count):
        if not self.is_mounted:
            return
        self._processing = False
        if ok:
            self.app.notify(f"{count} canciones devueltas al origen")
            self._load_tracks()
        else:
            self.query_one("#status", Static).update(
                "[red]✗ Error al deshacer. Re-autentícate (nuevos permisos requeridos).[/red]"
            )
