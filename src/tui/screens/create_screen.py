from rich.markup import escape
from textual import on
from textual.binding import Binding
from textual.containers import Vertical
from textual.screen import Screen
from textual.widgets import Button, Static

from ..widgets import TextInputModal, bordered_container


class CreateScreen(Screen):
    """Crear playlist en blanco: pide el nombre y la crea (privada)."""

    BINDINGS = [Binding("q", "back", "Volver")]

    CSS = """
    CreateScreen {
        align: center middle;
        padding: 1;
    }
    #box {
        width: 72;
        height: auto;
        padding: 1 2;
    }
    #status {
        height: auto;
        margin-top: 1;
    }
    #actions {
        height: auto;
        margin-top: 1;
        align-horizontal: center;
    }
    """

    def __init__(self):
        super().__init__()
        self._processing = False

    def action_back(self):
        self.app.pop_screen()

    def compose(self):
        with bordered_container(title="➕ Crear playlist", id="box"):
            yield Static(
                "Se creará una playlist en blanco (privada). Escribe el nombre:",
                markup=True,
            )
            yield Static("", id="status", markup=True)
            with Vertical(id="actions"):
                yield Button("Crear playlist...", id="create-btn", variant="primary")

    def on_mount(self):
        self.query_one("#create-btn", Button).focus()
        self._ask_name()

    def _ask_name(self):
        self.app.push_screen(
            TextInputModal(
                "➕ Crear playlist",
                "Nombre de la nueva playlist:",
                default="",
                confirm_label="Crear",
            ),
            callback=self._on_name,
        )

    @on(Button.Pressed, "#create-btn")
    def on_create_btn(self):
        if self._processing:
            return
        self._ask_name()

    def _on_name(self, name):
        if not self.is_mounted:
            return
        if name is None:
            return
        if not name.strip():
            self.app.notify("Escribe un nombre para la playlist", severity="warning")
            return
        self._processing = True
        self.query_one("#status", Static).update("Creando playlist...")
        clean = name.strip()

        def load():
            new_id = self.app.client.create_playlist(clean, public=False)
            self.app.call_from_thread(self._created, new_id, clean)

        self.run_worker(load, thread=True)

    def _created(self, new_id, name):
        if not self.is_mounted:
            return
        self._processing = False
        if new_id:
            self.query_one("#status", Static).update(
                f"[green]✓ Playlist '{escape(name)}' creada (privada).[/green]\n"
                "[dim]Ya puedes añadirle canciones desde 'Editar Playlist' o 'Mover canciones'.[/dim]"
            )
            self.app.notify(f"Playlist '{name}' creada")
        else:
            self.query_one("#status", Static).update(
                "[red]✗ Error al crear. Re-autentícate (nuevos permisos requeridos).[/red]"
            )
