from textual.binding import Binding
from textual.screen import Screen
from textual.widgets import OptionList, Static
from textual.widgets.option_list import Option

from ..widgets import bordered_container
from .cleanup_screen import CleanupScreen
from .create_screen import CreateScreen
from .edit_screen import EditScreen
from .export_screen import ExportScreen
from .import_screen import ImportScreen
from .merge_screen import MergeScreen
from .move_screen import MoveScreen
from .sort_screen import SortScreen
from .top_screen import TopScreen


class MainScreen(Screen):
    """Menú principal: OptionList en contenedor con borde y título."""

    BINDINGS = [Binding("q", "quit", "Salir")]

    CSS = """
    MainScreen {
        align: center middle;
    }
    #main-box {
        width: 72;
        height: auto;
        padding: 1 2;
    }
    #user-label {
        height: auto;
        margin-bottom: 1;
    }
    """

    def compose(self):
        with bordered_container(title="🎵 Spotify Manager", id="main-box"):
            yield Static(f"Conectado como: {self.app.user_name}", id="user-label")
            yield OptionList(
                Option("1. Editar Playlist", id="edit"),
                Option("2. Mover canciones a otra playlist", id="move"),
                Option("3. Crear playlist", id="create"),
                Option("4. CSV/TXT → Playlist (importar)", id="import"),
                Option("5. Limpiar playlist (avanzado)", id="cleanup"),
                Option("6. Fusionar / Dividir playlists", id="merge"),
                Option("7. Ordenar playlist", id="sort"),
                Option("8. Playlist → CSV/TXT (exportar)", id="export"),
                Option("9. Top artistas / canciones", id="top"),
                Option("10. Reautenticar", id="reauth"),
                Option("11. Cerrar", id="exit"),
            )

    def action_quit(self):
        self.app.exit()

    def on_option_list_option_selected(self, event):
        option_id = event.option.id
        if option_id == "edit":
            self.app.push_screen(EditScreen())
        elif option_id == "move":
            self.app.push_screen(MoveScreen())
        elif option_id == "create":
            self.app.push_screen(CreateScreen())
        elif option_id == "import":
            self.app.push_screen(ImportScreen())
        elif option_id == "cleanup":
            self.app.push_screen(CleanupScreen())
        elif option_id == "merge":
            self.app.push_screen(MergeScreen())
        elif option_id == "sort":
            self.app.push_screen(SortScreen())
        elif option_id == "export":
            self.app.push_screen(ExportScreen())
        elif option_id == "top":
            self.app.push_screen(TopScreen())
        elif option_id == "reauth":

            self.app.exit("reauth")
        elif option_id == "exit":
            self.app.exit()
