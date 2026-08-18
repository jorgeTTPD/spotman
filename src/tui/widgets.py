from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, DataTable, Input, Static


def apply_border(widget, title=""):
    
    widget.styles.border = ("round", "white")
    if title:
        widget.border_title = title
    return widget


def bordered_container(*children, title="", **kwargs):
    
    return apply_border(Vertical(*children, **kwargs), title)


def bordered_horizontal(*children, title="", **kwargs):
    
    return apply_border(Horizontal(*children, **kwargs), title)


def bordered_table(title="", **kwargs):
    
    return apply_border(DataTable(**kwargs), title)


def bordered_static(content="", title="", **kwargs):
    
    return apply_border(Static(content, **kwargs), title)


class PlaylistPicker(ModalScreen):
    

    BINDINGS = [Binding("q", "cancel", "Cancelar")]

    CSS = """
    PlaylistPicker {
        align: center middle;
    }
    #picker-box {
        width: 70%;
        height: 75%;
        padding: 1;
    }
    """

    def __init__(self, client, title="Elige playlist"):
        super().__init__()
        self.client = client
        self.dialog_title = title
        self.playlists = []

    def compose(self):
        with bordered_container(title=self.dialog_title, id="picker-box"):
            yield DataTable(id="picker-table", cursor_type="row", zebra_stripes=True)

    def on_mount(self):
        table = self.query_one("#picker-table", DataTable)
        table.add_column("Playlist")
        table.add_column("Tracks")

        def load():
            playlists = self.client.get_playlists() or []
            self.app.call_from_thread(self._populate, playlists)

        self.run_worker(load, thread=True)

    def _populate(self, playlists):
        if not self.is_mounted:
            return
        self.playlists = playlists
        table = self.query_one("#picker-table", DataTable)
        for p in playlists:
            total = (p.get("tracks") or p.get("items") or {}).get("total", 0)
            table.add_row(p.get("name", "?"), str(total))

    def on_data_table_row_selected(self, event):
        table = self.query_one("#picker-table", DataTable)
        index = table.get_row_index(event.row_key)
        if index is None:
            self.dismiss(None)
            return
        if 0 <= index < len(self.playlists):
            self.dismiss(self.playlists[index])
        else:
            self.dismiss(None)

    def action_cancel(self):
        self.dismiss(None)


class MultiPlaylistPicker(ModalScreen):
    

    BINDINGS = [
        Binding("q", "cancel", "Cancelar"),
        Binding("space", "toggle", "Marcar", show=False),
    ]

    CSS = """
    MultiPlaylistPicker {
        align: center middle;
    }
    #mpicker-box {
        width: 70%;
        height: 75%;
        padding: 1;
    }
    """

    def __init__(self, client, title="Elige playlists"):
        super().__init__()
        self.client = client
        self.dialog_title = title
        self.playlists = []
        self._selected = set()
        self._row_keys = {}
        self._marker_col = None

    def compose(self):
        with bordered_container(title=self.dialog_title, id="mpicker-box"):
            yield DataTable(id="mpicker-table", cursor_type="row", zebra_stripes=True)

    def on_mount(self):
        table = self.query_one("#mpicker-table", DataTable)
        self._marker_col = table.add_column("✓")
        table.add_column("Playlist")
        table.add_column("Tracks")

        def load():
            playlists = self.client.get_playlists() or []
            self.app.call_from_thread(self._populate, playlists)

        self.run_worker(load, thread=True)

    def _populate(self, playlists):
        if not self.is_mounted:
            return
        self.playlists = playlists
        table = self.query_one("#mpicker-table", DataTable)
        for i, p in enumerate(playlists):
            total = (p.get("tracks") or p.get("items") or {}).get("total", 0)
            rk = table.add_row("", p.get("name", "?"), str(total))
            self._row_keys[i] = rk

    def action_toggle(self):
        table = self.query_one("#mpicker-table", DataTable)
        index = table.cursor_row
        if index is None or not (0 <= index < len(self.playlists)):
            return
        rk = self._row_keys.get(index)
        if rk is None or self._marker_col is None:
            return
        if index in self._selected:
            self._selected.discard(index)
            table.update_cell(rk, self._marker_col, "", update_width=False)
        else:
            self._selected.add(index)
            table.update_cell(rk, self._marker_col, "✓", update_width=False)

    def on_data_table_row_selected(self, event):
        selected = [self.playlists[i] for i in sorted(self._selected)]
        self.dismiss(selected or None)

    def action_cancel(self):
        self.dismiss(None)


class TextInputModal(ModalScreen):
    

    BINDINGS = [Binding("escape", "cancel", "Cancelar")]

    CSS = """
    TextInputModal {
        align: center middle;
    }
    #input-box {
        width: 70%;
        height: auto;
        padding: 1 2;
    }
    #input-prompt {
        height: auto;
        margin-bottom: 1;
    }
    #input-field {
        margin-bottom: 1;
    }
    #input-buttons {
        height: auto;
        align-horizontal: center;
        margin-top: 1;
    }
    """

    def __init__(self, title, prompt, default="", confirm_label="OK"):
        super().__init__()
        self.dialog_title = title
        self.prompt = prompt
        self.default = default
        self.confirm_label = confirm_label

    def compose(self):
        with bordered_container(title=self.dialog_title, id="input-box"):
            yield Static(self.prompt, id="input-prompt")
            yield Input(value=self.default, id="input-field")
            with Horizontal(id="input-buttons"):
                yield Button(self.confirm_label, id="yes", variant="success")
                yield Button("Cancelar", id="no", variant="error")

    def on_mount(self):
        self.query_one("#input-field", Input).focus()

    def _value(self):
        return self.query_one("#input-field", Input).value.strip() or None

    def on_button_pressed(self, event):
        self.dismiss(self._value() if event.button.id == "yes" else None)

    def on_input_submitted(self, event):
        self.dismiss(self._value())

    def action_cancel(self):
        self.dismiss(None)


class ListPickerModal(ModalScreen):
    

    BINDINGS = [Binding("q", "cancel", "Cancelar")]

    CSS = """
    ListPickerModal {
        align: center middle;
    }
    #lpicker-box {
        width: 70%;
        height: 75%;
        padding: 1;
    }
    """

    def __init__(self, title="Elige opción", rows=None, col2="Cantidad"):
        super().__init__()
        self.dialog_title = title
        self.rows = rows or []
        self.col2 = col2

    def compose(self):
        with bordered_container(title=self.dialog_title, id="lpicker-box"):
            yield DataTable(id="lpicker-table", cursor_type="row", zebra_stripes=True)

    def on_mount(self):
        table = self.query_one("#lpicker-table", DataTable)
        table.add_column("Opción")
        table.add_column(self.col2)
        for label, count in self.rows:
            table.add_row(label, str(count))

    def on_data_table_row_selected(self, event):
        table = self.query_one("#lpicker-table", DataTable)
        index = table.get_row_index(event.row_key)
        if index is None:
            self.dismiss(None)
            return
        if 0 <= index < len(self.rows):
            self.dismiss(self.rows[index][0])
        else:
            self.dismiss(None)

    def action_cancel(self):
        self.dismiss(None)


class ConfirmScreen(ModalScreen):
    

    BINDINGS = [Binding("q", "cancel", "Cancelar")]

    CSS = """
    ConfirmScreen {
        align: center middle;
    }
    #confirm-box {
        width: 72%;
        height: auto;
        padding: 1 2;
    }
    #confirm-message {
        height: auto;
        max-height: 60%;
        overflow-y: auto;
    }
    #confirm-buttons {
        height: auto;
        align-horizontal: center;
        margin-top: 1;
    }
    """

    def __init__(self, title, message, confirm_label="Sí", cancel_label="No"):
        super().__init__()
        self.dialog_title = title
        self.message = message
        self.confirm_label = confirm_label
        self.cancel_label = cancel_label

    def compose(self):
        with bordered_container(title=self.dialog_title, id="confirm-box"):
            yield Static(self.message, id="confirm-message")
            with Horizontal(id="confirm-buttons"):
                yield Button(self.confirm_label, id="yes", variant="success")
                yield Button(self.cancel_label, id="no", variant="error")

    def on_button_pressed(self, event):
        self.dismiss(event.button.id == "yes")

    def action_cancel(self):
        self.dismiss(False)
