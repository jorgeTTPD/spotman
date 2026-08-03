from rich.markup import escape
from textual import on
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import Button, DataTable, Static

from ..widgets import ConfirmScreen, PlaylistPicker, bordered_container


class EditScreen(Screen):
    """Editar Playlist: selecciona canciones y elimínalas (con deshacer z)."""

    BINDINGS = [
        Binding("q", "back", "Volver"),
        Binding("space", "toggle_select", "Marcar", show=False),
        Binding("a", "select_all", "Todo", show=False),
        Binding("d", "deselect_all", "Nada", show=False),
        Binding("i", "invert_selection", "Invertir", show=False),
        Binding("x", "delete_selected", "Eliminar", show=False),
        Binding("z", "undo", "Deshacer", show=False),
    ]

    CSS = """
    EditScreen {
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
        self._playlist = None
        self._tracks = []
        self._row_keys = {}      # índice -> RowKey
        self._marker_col = None
        self._selected = set()   # URIs seleccionadas
        self._undo = []          # pila de (playlist_id, uris)
        self._processing = False

    def action_back(self):
        self.app.pop_screen()

    def compose(self):
        with Vertical(id="wrap"):
            with bordered_container(title="Canciones", id="tracks-box"):
                yield DataTable(
                    id="tracks-table", cursor_type="row", zebra_stripes=True
                )
            yield Static(
                "Elige una playlist y marca canciones con espacio.",
                id="status",
                markup=True,
            )
            with Horizontal(id="actions"):
                yield Button("Elegir playlist...", id="pick-pl", variant="primary")
                yield Button("Eliminar selección", id="del-btn", variant="error")

    def on_mount(self):
        self.query_one("#tracks-table", DataTable).focus()
        self._pick_playlist()

    def _pick_playlist(self):
        self.app.push_screen(
            PlaylistPicker(self.app.client, title="Elige playlist"),
            callback=self._on_picked,
        )

    @on(Button.Pressed, "#pick-pl")
    def on_pick_pl(self):
        self._pick_playlist()

    def _on_picked(self, playlist):
        if not self.is_mounted:
            return
        if playlist is None:
            return
        self._playlist = playlist
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
            tracks = self.app.client.get_playlist_tracks(self._playlist["id"]) or []
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
        if not self._playlist:
            status.update("Elige una playlist para editar.")
            return
        sel = len(self._selected)
        status.update(
            f"[bold]{escape(self._playlist.get('name', '?'))}[/bold] — "
            f"{len(self._tracks)} tracks | [cyan]{sel} seleccionadas[/cyan]\n"
            "[dim]espacio marcar · a todo · d nada · i invertir · "
            "x eliminar · z deshacer[/dim]"
        )

    # ------------------------------------------------------------------
    # Eliminar
    # ------------------------------------------------------------------

    @on(Button.Pressed, "#del-btn")
    def on_del_btn(self):
        self._confirm_delete()

    def action_delete_selected(self):
        if not self._tracks_focused():
            return
        self._confirm_delete()

    def _confirm_delete(self):
        if self._processing or not self._playlist:
            return
        uris = self._selected_uris()
        if not uris:
            self.app.notify("No hay canciones seleccionadas", severity="warning")
            return
        self.app.push_screen(
            ConfirmScreen(
                "🗑 Eliminar selección",
                f"¿Eliminar {len(uris)} canciones de "
                f"'{escape(self._playlist.get('name', '?'))}'?",
                confirm_label="Eliminar",
            ),
            callback=lambda ok: self._do_delete(ok, uris),
        )

    def _do_delete(self, ok, uris):
        if not self.is_mounted or not ok:
            return
        self._processing = True
        self.query_one("#status", Static).update("Eliminando...")
        pl = self._playlist

        def load():
            result = self.app.client.remove_tracks(pl["id"], uris)
            self.app.call_from_thread(self._deleted, result, pl, uris)

        self.run_worker(load, thread=True)

    def _deleted(self, ok, pl, uris):
        if not self.is_mounted:
            return
        self._processing = False
        if ok:
            self._undo.append((pl["id"], uris))
            if len(self._undo) > 20:
                self._undo.pop(0)
            self.app.notify(f"{len(uris)} canciones eliminadas")
            self._load_tracks()
        else:
            self.query_one("#status", Static).update(
                "[red]✗ Error al eliminar. Re-autentícate (nuevos permisos requeridos).[/red]"
            )

    # ------------------------------------------------------------------
    # Deshacer
    # ------------------------------------------------------------------

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
            self.app.notify(f"{count} canciones restauradas")
            self._load_tracks()
        else:
            self.query_one("#status", Static).update(
                "[red]✗ Error al deshacer. Re-autentícate (nuevos permisos requeridos).[/red]"
            )
