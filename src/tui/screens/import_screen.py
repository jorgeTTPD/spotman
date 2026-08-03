import os

from textual import on
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import (
    Button,
    DataTable,
    Input,
    ProgressBar,
    Static,
)

from ... import config
from ...csv_handler import read_tracks, read_uris
from ..widgets import bordered_container


class ImportScreen(Screen):
    """CSV/TXT → Playlist: selección de archivo, resolución y creación."""

    BINDINGS = [Binding("q", "back", "Volver")]

    CSS = """
    ImportScreen {
        padding: 1;
    }
    #files-box {
        height: auto;
        max-height: 14;
    }
    #resolve-box {
        height: auto;
    }
    #not-found {
        height: auto;
        max-height: 8;
    }
    #name-input {
        margin-top: 1;
    }
    #summary {
        margin-top: 1;
    }
    """

    def __init__(self):
        super().__init__()
        self.files = []
        self._uris = []
        self._not_found = []
        self._path = None

    def action_back(self):
        self.app.pop_screen()

    def compose(self):
        with Vertical():
            with bordered_container(title="Archivos en data/csv", id="files-box"):
                yield DataTable(
                    id="files-table", cursor_type="row", zebra_stripes=True
                )
            yield Input(
                placeholder="O ruta manual (CSV/TXT)...",
                id="manual-path",
            )
            with bordered_container(title="Resolviendo canciones", id="resolve-box"):
                yield ProgressBar(id="progress", show_percentage=True)
                yield Static("", id="progress-text")
                yield Static("", id="not-found", markup=True)
            yield Input(placeholder="Nombre de la playlist", id="name-input")
            with Horizontal():
                yield Button("Crear playlist", id="create-btn", variant="primary", disabled=True)
                yield Button("Reintentar", id="retry-btn", disabled=True)
            yield Static("", id="summary", markup=True)

    def on_mount(self):
        table = self.query_one("#files-table", DataTable)
        table.add_column("Archivo")
        table.add_column("Tipo")
        try:
            names = sorted(
                n
                for n in os.listdir(config.CSV_DIR)
                if n.lower().endswith((".csv", ".txt"))
            )
        except OSError:
            names = []
        self.files = names
        for n in self.files:
            ext = os.path.splitext(n)[1].lstrip(".").upper()
            table.add_row(n, ext)
        table.add_row("[ruta manual...]", "")

    @on(DataTable.RowSelected, "#files-table")
    def on_file_selected(self, event):
        table = self.query_one("#files-table", DataTable)
        index = table.get_row_index(event.row_key)
        if index is None:
            return
        if 0 <= index < len(self.files):
            self._start_import(os.path.join(config.CSV_DIR, self.files[index]))
        else:
            self.query_one("#manual-path", Input).focus()

    def on_input_submitted(self, event):
        if event.input.id == "manual-path":
            path = event.input.value.strip()
            if path:
                self._start_import(path)
        elif event.input.id == "name-input":
            self._create_playlist()

    def on_button_pressed(self, event):
        if event.button.id == "create-btn":
            self._create_playlist()
        elif event.button.id == "retry-btn" and self._path:
            self._start_import(self._path)

    def _start_import(self, path):
        self._path = path
        self.query_one("#create-btn", Button).disabled = True
        self.query_one("#retry-btn", Button).disabled = True
        self.query_one("#summary", Static).update("")
        try:
            tracks, kind = read_tracks(path)
        except OSError as e:
            self.query_one("#summary", Static).update(f"[red]Error: {e}[/red]")
            return
        if kind == "txt":
            uris = read_uris(path)
            if uris:
                self._uris = uris
                self._not_found = []
                self._finish_resolution(uris, [])
                return
        self._resolve_tracks(tracks or [])

    def _resolve_tracks(self, tracks):
        total = len(tracks)
        bar = self.query_one("#progress", ProgressBar)
        bar.update(total=total, progress=0)
        self.query_one("#progress-text", Static).update(
            f"Resolviendo 0/{total}..."
        )

        def load():
            uris, not_found = [], []
            for i, t in enumerate(tracks, 1):
                uri = self.app.client.search_track(t["artist"], t["name"])
                if uri:
                    uris.append(uri)
                else:
                    not_found.append(f"{t['artist']} - {t['name']}")
                self.app.call_from_thread(self._on_progress, i, total)
            self.app.call_from_thread(self._finish_resolution, uris, not_found)

        self.run_worker(load, thread=True)

    def _on_progress(self, done, total):
        if not self.is_mounted:
            return
        bar = self.query_one("#progress", ProgressBar)
        bar.update(total=total, progress=done)
        self.query_one("#progress-text", Static).update(
            f"Resolviendo {done}/{total}..."
        )

    def _finish_resolution(self, uris, not_found):
        if not self.is_mounted:
            return
        self._uris = uris
        self._not_found = not_found
        total = len(self._uris) + len(self._not_found)
        bar = self.query_one("#progress", ProgressBar)
        bar.update(total=total, progress=len(self._uris))
        self.query_one("#progress-text", Static).update(
            f"Encontradas {len(self._uris)}/{total}"
        )
        nf = self.query_one("#not-found", Static)
        if self._not_found:
            lines = "\n".join(f"• {x}" for x in self._not_found[:12])
            more = (
                f"\n... y {len(self._not_found) - 12} más"
                if len(self._not_found) > 12
                else ""
            )
            nf.update(f"[yellow]No encontradas:[/yellow]\n{lines}{more}")
        else:
            nf.update("[green]✓ Todas encontradas[/green]")
        self.query_one("#create-btn", Button).disabled = False
        self.query_one("#retry-btn", Button).disabled = False

    def _create_playlist(self):
        name = self.query_one("#name-input", Input).value.strip()
        if not name:
            self.app.notify("Escribe un nombre para la playlist", severity="warning")
            return
        if not self._uris:
            self.app.notify("No hay tracks para añadir", severity="warning")
            return
        self.query_one("#create-btn", Button).disabled = True

        def load():
            playlist_id = self.app.client.create_playlist(name, public=False)
            ok = False
            if playlist_id:
                ok = self.app.client.add_tracks(playlist_id, self._uris)
            self.app.call_from_thread(self._created, name, playlist_id, ok)

        self.run_worker(load, thread=True)

    def _created(self, name, playlist_id, ok):
        if not self.is_mounted:
            return
        summary = self.query_one("#summary", Static)
        if ok and playlist_id:
            extra = (
                f"  |  {len(self._not_found)} no encontradas"
                if self._not_found
                else ""
            )
            summary.update(
                f"[green]✓ Playlist '{name}' creada con {len(self._uris)} tracks.{extra}[/green]"
            )
            self.app.notify("Playlist creada")
            # Evitar crear la misma playlist dos veces
            self.query_one("#create-btn", Button).disabled = True
            self.query_one("#retry-btn", Button).disabled = True
            self.query_one("#name-input", Input).value = ""
            self._uris = []
        else:
            summary.update(
                "[red]✗ Error al crear. Re-autentícate (nuevos permisos requeridos).[/red]"
            )
            self.query_one("#create-btn", Button).disabled = False
