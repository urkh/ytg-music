from typing import Any, Optional

from gi.repository import Gtk

from models.media import HomeSection, parse_media_item
from services.worker import run_in_background
from services.ytmusic import api
from utils.ui_components import create_item_card, hide_error_page, on_card_clicked, show_error_page


@Gtk.Template(filename='ui/home.ui')
class HomeView(Gtk.Overlay):
    __gtype_name__ = 'HomeView'

    content_box = Gtk.Template.Child()
    spinner = Gtk.Template.Child()

    def __init__(self, app, **kwargs):
        super().__init__(**kwargs)
        self.app = app
        self.current_query = None
        self.load_data('home')

        app_instance = self.app.app if hasattr(self.app, 'app') else self.app
        if hasattr(app_instance, 'connect'):
            app_instance.connect('login-state-changed', self.on_login_state_changed)

    def on_login_state_changed(self, *args: Any) -> None:
        self.load_data('home')

    def load_data(self, query: Optional[str] = None) -> None:
        self.current_query = query

        self.content_box.set_visible(False)
        self.spinner.start()
        self.spinner.set_visible(True)

        def fetch():
            if query == 'home' or not query:
                return api.get_home(limit=4)
            else:
                return api.search(query, filter=None, limit=50)

        run_in_background(fetch, self.on_data_loaded)

    def on_data_loaded(self, data):
        self.spinner.stop()
        self.spinner.set_visible(False)

        if not data:
            show_error_page(self, self.content_box)
            return

        hide_error_page(self, self.content_box)
        self._render_data(data)

    def _render_data(self, data):
        while child := self.content_box.get_first_child():
            self.content_box.remove(child)

        is_home = isinstance(data, list) and len(data) > 0 and 'contents' in data[0]

        if is_home:
            self._render_home_sections(data)
        else:
            self._render_search_results(data)

    def _create_flowbox(self):
        flowbox = Gtk.FlowBox()
        flowbox.set_column_spacing(16)
        flowbox.set_row_spacing(16)
        flowbox.set_selection_mode(Gtk.SelectionMode.NONE)
        flowbox.set_max_children_per_line(10)
        flowbox.set_min_children_per_line(2)
        flowbox.set_homogeneous(True)
        flowbox.connect('child-activated', self.on_card_activated)
        return flowbox

    def on_card_activated(self, flowbox, child):
        box = child.get_child()
        if not hasattr(box, '_item'):
            return
        on_card_clicked(self.app, box._item)

    def _render_home_sections(self, data):
        for row in data:
            section = HomeSection.model_validate(row)

            if section.title:
                lbl_title = Gtk.Label(label=section.title)
                lbl_title.add_css_class('title-2')
                lbl_title.set_halign(Gtk.Align.START)
                self.content_box.append(lbl_title)

            if not section.contents:
                lbl_empty = Gtk.Label(label='(Empty)')
                lbl_empty.add_css_class('dim-label')
                lbl_empty.set_halign(Gtk.Align.START)
                self.content_box.append(lbl_empty)
                continue

            flowbox = self._create_flowbox()
            for item in section.contents:
                parsed_item = parse_media_item(item)
                card = create_item_card(self.app, parsed_item)
                if card:
                    flowbox.append(card)

            self.content_box.append(flowbox)

    def _render_search_results(self, data):
        flowbox = self._create_flowbox()
        for item in data:
            parsed_item = parse_media_item(item)
            card = create_item_card(self.app, parsed_item)
            if card:
                flowbox.append(card)

        self.content_box.append(flowbox)
