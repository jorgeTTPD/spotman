import os

from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import Button, RadioButton, RadioSet, Static

from ... import config
from ...csv_handler import sanitize_filename, write_csv, write_txt
from ..widgets import bordered_container, bordered_static, PlaylistPicker


class ExportScreen(Screen):
    

    BINDINGS = [Binding("q", "back", "Volver")]

    CSS = """
    ExportScreen {
        align: center middle;
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
            with bordered_container(title="Formato"):
                yield RadioSet(
                    RadioButton("CSV", id="csv"),
                    RadioButton("TXT", id="txt"),
                    id="format",
                )
            with Horizontal():
                yield Button("Exportar", id="export-btn", variant="primary")
                yield Button("Cambiar playlist", id="change-btn")
        yield bordered_static("", title="Estado", id="status")

    def on_mount(self):
        self._pick_playlist()

    def _pick_playlist(self):
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
            f"Playlist: {self._playlist.get('name', '?')} — {len(self._tracks)} tracks. Pulsa Exportar."
        )

    def on_button_pressed(self, event):
        if event.button.id == "export-btn":
            self._export()
        elif event.button.id == "change-btn":
            self._pick_playlist()

    def _format(self):
        rs = self.query_one("#format", RadioSet)
        return rs.pressed_button.id if rs.pressed_button else "csv"

    def _export(self):
        if not self._tracks:
            self.app.notify("Primero elige una playlist", severity="warning")
            return
        fmt = self._format()
        base = sanitize_filename(self._playlist.get("name", "playlist"))
        path = os.path.join(config.CSV_DIR, f"{base}.{fmt}")
        try:
            if fmt == "csv":
                write_csv(path, self._tracks)
            else:
                write_txt(path, self._tracks)
        except OSError as e:
            self.query_one("#status", Static).update(f"[red]Error: {e}[/red]")
            return
        self.query_one("#status", Static).update(
            f"[green]✓ Playlist exportada:[/green]\n[bold]{os.path.abspath(path)}[/bold]\n({len(self._tracks)} tracks)"
        )
        self.app.notify("Playlist exportada")
