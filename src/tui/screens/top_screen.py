from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import Button, DataTable, RadioButton, RadioSet, Static

from ..widgets import bordered_container, bordered_table

KINDS = [("Artistas", "artists"), ("Canciones", "tracks")]
RANGES = [
    ("4 semanas", "short_term"),
    ("6 meses", "medium_term"),
    ("Todo el tiempo", "long_term"),
]


class TopScreen(Screen):
    """Top artistas/canciones con creación de playlist desde el top."""

    BINDINGS = [Binding("q", "back", "Volver")]

    CSS = """
    TopScreen {
        padding: 1;
    }
    #top-table {
        height: 1fr;
        margin-top: 1;
    }
    #status {
        margin-top: 1;
    }
    """

    def __init__(self):
        super().__init__()
        self._items = []
        self._kind = "artists"

    def action_back(self):
        self.app.pop_screen()

    def compose(self):
        with Vertical():
            with Horizontal():
                with bordered_container(title="Tipo"):
                    yield RadioSet(
                        *[RadioButton(label, id=value) for label, value in KINDS],
                        id="kind",
                    )
                with bordered_container(title="Rango"):
                    yield RadioSet(
                        *[RadioButton(label, id=value) for label, value in RANGES],
                        id="range",
                    )
            yield bordered_table(
                title="Top 20",
                id="top-table",
                cursor_type="row",
                zebra_stripes=True,
            )
            yield Button("Crear playlist con este top", id="create-btn", variant="primary")
            yield Static("", id="status", markup=True)

    def on_mount(self):
        self._load()

    def on_radio_set_changed(self, event):
        self._load()

    def _params(self):
        kind_rs = self.query_one("#kind", RadioSet)
        range_rs = self.query_one("#range", RadioSet)
        kind = kind_rs.pressed_button.id if kind_rs.pressed_button else "artists"
        time_range = (
            range_rs.pressed_button.id if range_rs.pressed_button else "short_term"
        )
        return kind, time_range

    def _load(self):
        kind, time_range = self._params()
        self._kind = kind
        table = self.query_one("#top-table", DataTable)
        table.clear(columns=True)
        table.add_column("#")
        if kind == "artists":
            table.add_column("Artista")
        else:
            table.add_column("Artista")
            table.add_column("Título")
            table.add_column("Álbum")
        self.query_one("#status", Static).update("Cargando...")

        def load():
            items = self.app.client.get_top(kind, time_range, 20)
            self.app.call_from_thread(self._populate, items)

        self.run_worker(load, thread=True)

    def _populate(self, items):
        if not self.is_mounted:
            return
        self._items = items or []
        table = self.query_one("#top-table", DataTable)
        for i, item in enumerate(self._items, 1):
            if self._kind == "artists":
                table.add_row(str(i), item.get("name", "?"))
            else:
                artists = ", ".join(
                    a.get("name", "") for a in item.get("artists", [])
                )
                album = (item.get("album") or {}).get("name", "")
                table.add_row(str(i), artists, item.get("name", "?"), album)
        self.query_one("#status", Static).update(
            f"{len(self._items)} resultados"
        )

    def on_button_pressed(self, event):
        if event.button.id == "create-btn":
            self._create_playlist()

    def _create_playlist(self):
        uris = [t.get("uri") for t in self._items if t.get("uri")]
        if not uris:
            self.app.notify(
                "Selecciona 'Canciones' para poder crear la playlist",
                severity="warning",
            )
            return
        kind, time_range = self._params()
        kind_label = dict(KINDS).get(kind, kind)
        range_label = dict(RANGES).get(time_range, time_range)
        name = f"Top {kind_label} ({range_label})"
        self.query_one("#status", Static).update("Creando playlist...")

        def load():
            playlist_id = self.app.client.create_playlist(name, public=False)
            ok = False
            if playlist_id:
                ok = self.app.client.add_tracks(playlist_id, uris)
            self.app.call_from_thread(self._created, name, playlist_id, ok, len(uris))

        self.run_worker(load, thread=True)

    def _created(self, name, playlist_id, ok, count):
        if not self.is_mounted:
            return
        if ok and playlist_id:
            self.query_one("#status", Static).update(
                f"[green]✓ Playlist '{name}' creada con {count} tracks.[/green]"
            )
            self.app.notify("Playlist creada")
        else:
            self.query_one("#status", Static).update(
                "[red]✗ Error al crear. Re-autentícate (nuevos permisos requeridos).[/red]"
            )
