from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import Button, RadioButton, RadioSet, Static

from ..widgets import (
    bordered_container,
    bordered_static,
    ConfirmScreen,
    PlaylistPicker,
)

CRITERIA = [
    ("Título", "name"),
    ("Artista", "artist"),
    ("Álbum", "album"),
    ("Duración", "duration_ms"),
]
ORDERS = [
    ("Ascendente (A→Z)", "asc"),
    ("Descendente (Z→A)", "desc"),
]


class SortScreen(Screen):
    

    BINDINGS = [Binding("q", "back", "Volver")]

    CSS = """
    SortScreen {
        padding: 1;
    }
    #status {
        width: 90;
        height: auto;
        margin-top: 1;
        padding: 1 2;
    }
    """

    def __init__(self):
        super().__init__()
        self._playlist = None
        self._tracks = []

    def action_back(self):
        self.app.pop_screen()

    def compose(self):
        with Vertical():
            with Horizontal():
                with bordered_container(title="Criterio"):
                    yield RadioSet(
                        *[RadioButton(label, id=value) for label, value in CRITERIA],
                        id="criterion",
                    )
                with bordered_container(title="Orden"):
                    yield RadioSet(
                        *[RadioButton(label, id=value) for label, value in ORDERS],
                        id="order",
                    )
            yield Static(
                "⚠ Se quitarán y volverán a añadir los tracks en el nuevo orden",
                id="warning",
            )
            with Horizontal():
                yield Button("Ordenar", id="sort-btn", variant="primary")
                yield Button("Cancelar", id="cancel-btn")
        yield bordered_static("", title="Estado", id="status")

    def on_mount(self):
        self.app.push_screen(
            PlaylistPicker(self.app.client, title="Elige playlist"),
            callback=self._on_picked,
        )

    def _on_picked(self, playlist):
        if not self.is_mounted:
            return
        if playlist is None:
            self.app.pop_screen()
            return
        self._playlist = playlist
        self.query_one("#status", Static).update(
            f"Cargando '{playlist.get('name', '?')}'..."
        )

        def load():
            tracks = self.app.client.get_playlist_tracks(playlist["id"])
            self.app.call_from_thread(self._loaded, tracks)

        self.run_worker(load, thread=True)

    def _loaded(self, tracks):
        if not self.is_mounted:
            return
        self._tracks = tracks or []
        self.query_one("#status", Static).update(
            f"Playlist: {self._playlist.get('name', '?')} — {len(self._tracks)} tracks. Elige criterio y pulsa Ordenar."
        )

    def _criterion(self):
        rs = self.query_one("#criterion", RadioSet)
        return rs.pressed_button.id if rs.pressed_button else "name"

    def _reverse(self):
        rs = self.query_one("#order", RadioSet)
        return bool(rs.pressed_button and rs.pressed_button.id == "desc")

    def on_button_pressed(self, event):
        if event.button.id == "sort-btn":
            self._confirm()
        elif event.button.id == "cancel-btn":
            self.app.pop_screen()

    def _confirm(self):
        if not self._tracks:
            self.app.notify("Primero elige una playlist", severity="warning")
            return
        self.app.push_screen(
            ConfirmScreen(
                "⚠️ Ordenar playlist",
                "Se quitarán y volverán a añadir los tracks en el nuevo orden.",
                confirm_label="Ordenar",
            ),
            callback=self._on_confirm,
        )

    def _on_confirm(self, confirmed):
        if not self.is_mounted or not confirmed:
            return
        key = self._criterion()
        reverse = self._reverse()
        if key == "duration_ms":
            sorted_tracks = sorted(
                self._tracks, key=lambda t: t.get("duration_ms", 0), reverse=reverse
            )
        else:
            sorted_tracks = sorted(
                self._tracks,
                key=lambda t: (t.get(key, "") or "").lower(),
                reverse=reverse,
            )
        uris = [t["uri"] for t in sorted_tracks if t.get("uri")]
        self.query_one("#status", Static).update("Reordenando...")

        def load():
            removed = self.app.client.remove_tracks(self._playlist["id"], uris)
            added = (
                self.app.client.add_tracks(self._playlist["id"], uris)
                if removed
                else False
            )
            self.app.call_from_thread(self._done, removed, added)

        self.run_worker(load, thread=True)

    def _done(self, removed, added):
        if not self.is_mounted:
            return
        status = self.query_one("#status", Static)
        if removed and added:
            status.update(
                f"[green]✓ Playlist reordenada ({len(self._tracks)} tracks).[/green]"
            )
            self.app.notify("Playlist reordenada")
        elif removed and not added:
            status.update(
                "[red]✗ Se quitaron los tracks pero falló volver a añadirlos. "
                "La playlist puede estar vacía. Re-autentícate y reintenta.[/red]"
            )
        else:
            status.update(
                "[red]✗ Error al reordenar. Re-autentícate (nuevos permisos requeridos).[/red]"
            )
