from gi.repository import Gtk

from models.media import LibrarySection, parse_media_item
from services.worker import run_in_background
from services.ytmusic import api
from utils.logger import get_logger
from utils.ui_components import create_item_card, hide_error_page, on_card_clicked, show_error_page

logger = get_logger(__name__)


@Gtk.Template(filename='ui/library.ui')
class LibraryView(Gtk.Overlay):
    __gtype_name__ = 'LibraryView'

    content_box = Gtk.Template.Child()
    spinner = Gtk.Template.Child()

    def __init__(self, app, **kwargs):
        super().__init__(**kwargs)
        self.app = app

    def load_data(self):
        self.content_box.set_visible(False)
        self.spinner.start()
        self.spinner.set_visible(True)

        def fetch():
            sections_def = [
                (api.get_library_playlists, 'Your Playlists', 'playlist'),
                (api.get_library_albums, 'Your Albums', 'album'),
                (api.get_library_songs, 'Saved Songs', 'song'),
            ]
            rows = []
            for func, title, force_type in sections_def:
                try:
                    res = func(limit=15)
                    if res:
                        rows.append(LibrarySection(title=title, contents=res, force_type=force_type))
                except Exception as e:
                    logger.error(f'Error loading {title.lower()} from library: {e}')
            return rows

        run_in_background(fetch, self.on_data_loaded)

    def on_data_loaded(self, data):
        self.spinner.stop()
        self.spinner.set_visible(False)

        if not data:
            show_error_page(self, self.content_box)
            return

        hide_error_page(self, self.content_box)
        self._render_data(data)

    def _render_data(self, sections):
        while child := self.content_box.get_first_child():
            self.content_box.remove(child)

        for section in sections:
            self._add_section(section.title, section.contents, section.force_type)

    def _add_section(self, title, items, force_type):
        if not items:
            return

        lbl = Gtk.Label(label=title)
        lbl.add_css_class('title-2')
        lbl.set_halign(Gtk.Align.START)
        lbl.set_margin_bottom(12)

        flowbox = self._create_flowbox()

        self.content_box.append(lbl)

        for item in items:
            parsed_item = parse_media_item(item, force_type=force_type)
            card = create_item_card(self.app, parsed_item)
            if card:
                flowbox.append(card)

        self.content_box.append(flowbox)

    def _create_flowbox(self):
        flowbox = Gtk.FlowBox()
        flowbox.set_valign(Gtk.Align.START)
        flowbox.set_max_children_per_line(20)
        flowbox.set_selection_mode(Gtk.SelectionMode.NONE)
        flowbox.connect('child-activated', self.on_card_activated)
        return flowbox

    def on_card_activated(self, flowbox, child):
        box = child.get_child()
        if not hasattr(box, '_item'):
            return

        on_card_clicked(self.app, box._item)
