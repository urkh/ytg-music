from gi.repository import Gtk

from models.media import ExploreData, parse_media_item
from services.worker import run_in_background
from services.ytmusic import api
from utils.logger import get_logger
from utils.ui_components import create_item_card, hide_error_page, on_card_clicked, show_error_page

logger = get_logger(__name__)


@Gtk.Template(filename='ui/explore.ui')
class ExploreView(Gtk.Overlay):
    __gtype_name__ = 'ExploreView'

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
            return api.get_explore()

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

        explore_data = ExploreData.model_validate(data)

        if explore_data.new_releases:
            items = [parse_media_item(item, force_type='album') for item in explore_data.new_releases]
            self._add_section('New Releases', items)

        if explore_data.trending and explore_data.trending.items:
            items = [parse_media_item(item, force_type='video') for item in explore_data.trending.items]
            self._add_section('Trending', items)

        if explore_data.moods_and_genres:
            lbl = Gtk.Label(label='Genres')
            lbl.add_css_class('title-2')
            lbl.set_halign(Gtk.Align.START)
            lbl.set_margin_bottom(12)
            self.content_box.append(lbl)

            flowbox = Gtk.FlowBox()
            flowbox.set_valign(Gtk.Align.START)
            flowbox.set_max_children_per_line(10)
            flowbox.set_selection_mode(Gtk.SelectionMode.NONE)
            flowbox.set_column_spacing(8)
            flowbox.set_row_spacing(8)

            for mood in explore_data.moods_and_genres:
                btn = Gtk.Button(label=mood.title)
                btn.add_css_class('pill')
                btn.connect('clicked', self.on_mood_clicked, mood.params)
                flowbox.append(btn)

            self.content_box.append(flowbox)

    def _add_section(self, title, items):
        if not items:
            return

        lbl = Gtk.Label(label=title)
        lbl.add_css_class('title-2')
        lbl.set_halign(Gtk.Align.START)
        lbl.set_margin_bottom(12)

        flowbox = Gtk.FlowBox()
        flowbox.set_valign(Gtk.Align.START)
        flowbox.set_max_children_per_line(20)
        flowbox.set_selection_mode(Gtk.SelectionMode.NONE)
        flowbox.connect('child-activated', self.on_card_activated)

        self.content_box.append(lbl)

        for item in items:
            card = create_item_card(self.app, item)
            if card:
                flowbox.append(card)

        self.content_box.append(flowbox)

    def on_card_activated(self, flowbox, child):
        box = child.get_child()
        if not hasattr(box, '_item'):
            return

        on_card_clicked(self.app, box._item)

    def on_mood_clicked(self, button, params):
        logger.info(f'Mood selected: {params}')
