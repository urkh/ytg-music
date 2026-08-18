from gi.repository import Adw, GLib, Gtk

from services.worker import run_in_background
from services.ytmusic import api
from utils.memory import free_memory
from views.album import AlbumView
from views.artist import ArtistView
from views.explore import ExploreView
from views.home import HomeView
from views.library import LibraryView
from views.player import PlayerView
from views.queue import QueueView
from views.sidebar import SidebarView


@Gtk.Template(filename='ui/window.ui')
class MainWindow(Adw.ApplicationWindow):
    __gtype_name__ = 'MainWindow'

    main_stack = Gtk.Template.Child()
    queue_split_view = Gtk.Template.Child()

    player_container = Gtk.Template.Child()
    queue_container = Gtk.Template.Child()
    header_queue_switcher_container = Gtk.Template.Child()
    sidebar_container = Gtk.Template.Child()
    home_container = Gtk.Template.Child()
    library_container = Gtk.Template.Child()
    explore_container = Gtk.Template.Child()
    album_container = Gtk.Template.Child()
    artist_container = Gtk.Template.Child()

    btn_back = Gtk.Template.Child()
    split_view = Gtk.Template.Child()
    btn_toggle_sidebar = Gtk.Template.Child()
    main_search_entry = Gtk.Template.Child()

    def __init__(self, app, **kwargs):
        super().__init__(**kwargs)
        self.app = app

        self.main_stack.set_visible_child_name('home')

        self.player_view = PlayerView(self)
        self.player_container.append(self.player_view)

        # Playback queue
        while child := self.queue_container.get_first_child():
            self.queue_container.remove(child)

        self.queue_view = QueueView(self)
        self.queue_container.append(self.queue_view)

        self.sidebar_view = SidebarView(self)
        self.sidebar_container.append(self.sidebar_view)

        self.home_view = HomeView(self)
        self.home_container.append(self.home_view)

        self.library_view = None
        self.explore_view = None
        self.album_view = None
        self.artist_view = None

        self.navigation_history = []

        self.main_search_entry.connect('search-changed', self.on_search_changed)

        self.search_popover = Gtk.Popover()
        self.search_popover.set_parent(self.main_search_entry)
        self.search_popover.set_position(Gtk.PositionType.BOTTOM)
        self.search_popover.set_autohide(False)
        self.search_popover.set_has_arrow(False)

        self.main_search_entry.connect('notify::has-focus', self.on_search_focus_changed)

        self.suggestion_list = Gtk.ListBox()
        self.suggestion_list.set_selection_mode(Gtk.SelectionMode.NONE)
        self.suggestion_list.add_css_class('navigation-sidebar')
        self.suggestion_list.connect('row-activated', self.on_suggestion_activated)

        scroll = Gtk.ScrolledWindow()
        scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scroll.set_propagate_natural_height(True)
        scroll.set_max_content_height(850)
        scroll.set_min_content_width(470)
        scroll.set_child(self.suggestion_list)

        self.search_popover.set_child(scroll)
        self.pending_search_id = 0
        self._ignore_search_changed = False

        self.sidebar_view.nav_list.connect('row-activated', self.on_nav_row_activated)

        stack_gesture = Gtk.GestureClick.new()
        stack_gesture.set_propagation_phase(Gtk.PropagationPhase.CAPTURE)
        stack_gesture.connect('pressed', lambda *args: self.search_popover.popdown())
        self.main_stack.add_controller(stack_gesture)

    def on_search_focus_changed(self, entry, param):
        if not entry.has_focus():
            GLib.timeout_add(150, self.search_popover.popdown)

    def on_nav_row_activated(self, listbox, row):
        page_name = row.get_name()
        if page_name:
            if page_name == 'row_home':
                self.main_search_entry.set_text('')
                page_name = 'home'
            self.navigate_to(page_name)
            if self.split_view.get_collapsed():
                self.split_view.set_show_sidebar(False)

    @Gtk.Template.Callback()
    def on_search_activate(self, entry):
        self._search_submitted = True
        self.search_popover.popdown()
        if self.pending_search_id:
            GLib.source_remove(self.pending_search_id)
            self.pending_search_id = 0

        query = entry.get_text().strip()
        self._last_searched_text = query

        self.navigate_to('home')
        if hasattr(self, 'home_view'):
            if query:
                self.home_view.load_data(query)
            else:
                self.home_view.load_data('home')

    def on_search_changed(self, entry):
        if getattr(self, '_ignore_search_changed', False):
            return

        text = entry.get_text().strip()

        if getattr(self, '_last_searched_text', None) == text:
            return

        self._search_submitted = False

        if self.pending_search_id:
            GLib.source_remove(self.pending_search_id)
            self.pending_search_id = 0

        if not text:
            self.search_popover.popdown()
            if hasattr(self, 'home_view') and self.home_view.current_query != 'home':
                self.navigate_to('home')
                self.home_view.load_data('home')
            return

        self.pending_search_id = GLib.timeout_add(500, self.fetch_suggestions, text)

    def fetch_suggestions(self, query):
        self.pending_search_id = 0

        def fetch():
            try:
                return api.get_search_suggestions(query)
            except Exception:
                return []

        def on_loaded(suggestions):
            if getattr(self, '_search_submitted', False):
                return

            if not suggestions:
                self.search_popover.popdown()
                return

            # Get existing rows
            existing_rows = []
            child = self.suggestion_list.get_first_child()
            while child:
                existing_rows.append(child)
                child = child.get_next_sibling()

            for i, sug in enumerate(suggestions):
                if i < len(existing_rows):
                    row = existing_rows[i]
                    row._lbl.set_label(sug)
                    row._suggestion = sug
                    row.set_visible(True)
                else:
                    lbl = Gtk.Label(label=sug, xalign=0)
                    row = Gtk.ListBoxRow()

                    box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
                    box.set_margin_start(26)
                    box.set_margin_end(26)
                    box.set_margin_top(2)
                    box.set_margin_bottom(2)

                    icon = Gtk.Image.new_from_icon_name('system-search-symbolic')
                    icon.set_margin_end(12)
                    icon.add_css_class('dim-label')

                    box.append(icon)
                    box.append(lbl)
                    row.set_child(box)

                    row._lbl = lbl
                    row._suggestion = sug

                    self.suggestion_list.append(row)

            # Hide extra rows
            for i in range(len(suggestions), len(existing_rows)):
                existing_rows[i].set_visible(False)

            self.search_popover.popup()

        run_in_background(fetch, on_loaded)
        return False

    def on_suggestion_activated(self, listbox, row):
        if not hasattr(row, '_suggestion'):
            return
        suggestion = row._suggestion
        self._ignore_search_changed = True
        self.search_popover.popdown()
        self.main_search_entry.set_text(suggestion)
        self.main_search_entry.set_position(-1)
        self._ignore_search_changed = False
        self.on_search_activate(self.main_search_entry)

    def navigate_to(self, view_name, **kwargs):
        current_view = self.main_stack.get_visible_child_name()

        if view_name == 'home':
            self.navigation_history.clear()
            self.btn_back.set_visible(False)
        else:
            if current_view and current_view != view_name:
                self.navigation_history.append(current_view)
                self.btn_back.set_visible(True)

        if view_name == 'artist':
            artist_id = kwargs.get('artist_id')
            if self.artist_view is None:
                self.artist_view = ArtistView(self)
                self.artist_container.append(self.artist_view)
            if artist_id:
                self.artist_view.load_artist(artist_id)

        elif view_name == 'album':
            album_id = kwargs.get('album_id')
            if self.album_view is None:
                self.album_view = AlbumView(self)
                self.album_container.append(self.album_view)
            if album_id:
                self.album_view.load_album(album_id)

        elif view_name == 'library':
            if self.library_view is None:
                self.library_view = LibraryView(self)
                self.library_container.append(self.library_view)
            self.library_view.load_data()

        elif view_name == 'explore':
            if self.explore_view is None:
                self.explore_view = ExploreView(self)
                self.explore_container.append(self.explore_view)
            self.explore_view.load_data()

        self.main_stack.set_visible_child_name(view_name)
        GLib.idle_add(free_memory)

    @Gtk.Template.Callback()
    def on_back_clicked(self, btn):
        if self.navigation_history:
            prev_view = self.navigation_history.pop()
            self.main_stack.set_visible_child_name(prev_view)
            GLib.idle_add(free_memory)
            if not self.navigation_history:
                self.btn_back.set_visible(False)

    @Gtk.Template.Callback()
    def on_toggle_sidebar_clicked(self, button):
        current_state = self.split_view.get_show_sidebar()
        self.split_view.set_show_sidebar(not current_state)
