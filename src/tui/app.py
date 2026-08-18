from textual.app import App


from . import transparent

from .auth import show_auth
from .console import console
from .screens.main_screen import MainScreen
from .setup import run_setup
from .. import config
from ..spotify_client import SpotifyClient


transparent.apply_patches()


class SpotifyManagerApp(App):
    

    TITLE = "🎵 Spotify Manager"
    SUB_TITLE = "Gestor de playlists"


    CSS = """
    App {
        background: transparent;
    }
    Screen {
        background: transparent;
    }
    Screen > * {
        background: transparent;
    }
    Container, Vertical, Horizontal, ScrollableContainer {
        background: transparent;
    }
    DataTable, RadioSet, RadioButton, Input, Button, Static, OptionList,
    ListView, ListItem {
        background: transparent;
    }
    DataTable:focus, OptionList:focus {
        background-tint: transparent;
    }
    Scrollbar {
        scrollbar-background: transparent;
        scrollbar-background-active: transparent;
        scrollbar-background-hover: transparent;
    }
    """

    def __init__(self, client, user_name):
        super().__init__()
        self.client = client
        self.user_name = user_name

    def on_mount(self):

        self.client.silent = True
        self.push_screen(MainScreen())


def run():
    if not config.has_credentials():
        console.print()
        if not run_setup(console):
            return
        client = SpotifyClient()
        user = show_auth(client)
        if not user:
            return
    else:
        client = SpotifyClient()
        user = client.authenticate()
        if not user:
            console.print("[yellow]No se pudo autenticar con Spotify.[/yellow]\n")
            choice = console.input("¿Reintentar autenticación? (s/N): ").strip().lower()
            if choice in ("s", "si", "y", "yes"):
                user = show_auth(client)
                if not user:
                    return
            else:
                return

    while True:
        user_name = user.get("display_name", user["id"]) if user else "?"
        result = SpotifyManagerApp(client, user_name).run()
        if result != "reauth":
            break

        console.print()
        console.print("[yellow]🔑 Reautenticando con Spotify...[/yellow]")
        client.silent = False
        new_user = show_auth(client)
        if not new_user:

            console.print(
                "[dim]Reautenticación cancelada, continúas con tu sesión actual.[/dim]"
            )
            continue
        user = new_user
