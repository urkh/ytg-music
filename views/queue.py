from gi.repository import Adw, GLib, Gtk, Pango

from services.image_loader import load_image_async
from services.player_service import player_service
from services.worker import run_in_background
from services.ytmusic import api
from utils.logger import get_logger

logger = get_logger(__name__)


@Gtk.Template(filename='ui/queue.ui')
class QueueView(Gtk.Box):
    __gtype_name__ = 'QueueView'

    stack = Gtk.Template.Child()
    queue_container = Gtk.Template.Child()
    listbox = Gtk.Template.Child()
    lyrics_container = Gtk.Template.Child()
    lyrics_scroll = Gtk.Template.Child()
    lyrics_box = Gtk.Template.Child()
    lyrics_spinner = Gtk.Template.Child()
    lyrics_label = Gtk.Template.Child()
    similar_container = Gtk.Template.Child()
    similar_listbox = Gtk.Template.Child()

    def __init__(self, app, **kwargs):
        super().__init__(**kwargs)
        self.app = app

        self.switcher = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
        self.switcher.add_css_class('linked')
        self.switcher.set_halign(Gtk.Align.CENTER)

        def create_tab_btn(label_text, icon_name):
            btn = Gtk.ToggleButton()
            box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
            icon = Gtk.Image.new_from_icon_name(icon_name)
            lbl = Gtk.Label(label=label_text)
            lbl.add_css_class('caption')
            box.append(icon)
            box.append(lbl)
            btn.set_child(box)
            return btn

        btn_queue = create_tab_btn('', 'view-list-symbolic')
        btn_lyrics = create_tab_btn('', 'text-x-generic-symbolic')
        btn_similar = create_tab_btn('', 'system-users-symbolic')

        self.switcher.append(btn_queue)
        self.switcher.append(btn_lyrics)
        self.switcher.append(btn_similar)

        self._is_toggling = False

        def on_toggle(btn, name):
            if self._is_toggling:
                return

            self._is_toggling = True
            if btn.get_active():
                for other in [btn_queue, btn_lyrics, btn_similar]:
                    if other != btn:
                        other.set_active(False)

                self.stack.set_visible_child_name(name)
                if hasattr(self.app, 'queue_container'):
                    self.app.queue_container.set_visible(True)
            else:
                if not any(b.get_active() for b in [btn_queue, btn_lyrics, btn_similar]):
                    if hasattr(self.app, 'queue_container'):
                        self.app.queue_container.set_visible(False)
            self._is_toggling = False

        btn_queue.connect('toggled', on_toggle, 'queue')
        btn_lyrics.connect('toggled', on_toggle, 'lyrics')
        btn_similar.connect('toggled', on_toggle, 'similar')

        if hasattr(self.app, 'header_queue_switcher_container'):
            self.app.header_queue_switcher_container.append(self.switcher)

        self.current_lyrics_video_id = None

        self.current_similar_artist_id = None

        player_service.connect('queue-changed', self.on_queue_changed)
        player_service.connect('queue-index-changed', self.on_index_changed)

        self.listbox.connect('row-activated', self.on_row_activated)
        self.similar_listbox.connect('row-activated', self.on_similar_activated)

    def create_placeholder(self, title, text):
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        status = Adw.StatusPage(icon_name='emblem-documents-symbolic', title=title, description=text)
        box.append(status)
        return box

    def on_queue_changed(self, service):
        while row := self.listbox.get_first_child():
            self.listbox.remove(row)

        for idx, track in enumerate(player_service.queue):
            row = Gtk.ListBoxRow()
            row.queue_index = idx

            box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
            box.set_margin_start(12)
            box.set_margin_end(12)
            box.set_margin_top(8)
            box.set_margin_bottom(8)

            img = Gtk.Image.new_from_icon_name('audio-x-generic-symbolic')
            img.set_pixel_size(36)
            box.append(img)

            thumbnails = track.get('thumbnails', [])
            thumb_url = thumbnails[-1].get('url') if thumbnails else None
            if thumb_url:
                load_image_async(thumb_url, img)

            vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
            vbox.set_valign(Gtk.Align.CENTER)
            vbox.set_hexpand(True)

            title = track.get('title', 'Unknown')
            title_lbl = Gtk.Label(label=title, xalign=0)
            title_lbl.add_css_class('heading')
            title_lbl.set_ellipsize(Pango.EllipsizeMode.END)
            vbox.append(title_lbl)
            row.title_label = title_lbl

            artists = track.get('artists', [])
            artist_name = artists[0].get('name', 'Artist') if (artists and isinstance(artists, list)) else 'Artist'
            artist_id = artists[0].get('id') if (artists and isinstance(artists, list)) else None

            if artist_id:
                escaped_artist = GLib.markup_escape_text(artist_name)
                artist_lbl = Gtk.Label(xalign=0)
                artist_lbl.set_markup(f"<a href='{artist_id}' title='Go to artist'>{escaped_artist}</a>")
                artist_lbl.add_css_class('dim-label')
                artist_lbl.set_ellipsize(Pango.EllipsizeMode.END)
                artist_lbl.connect('activate-link', self.on_artist_link_clicked)
                vbox.append(artist_lbl)
            else:
                artist_lbl = Gtk.Label(label=artist_name, xalign=0)
                artist_lbl.add_css_class('dim-label')
                artist_lbl.set_ellipsize(Pango.EllipsizeMode.END)
                vbox.append(artist_lbl)

            box.append(vbox)
            row.set_child(box)
            row.set_activatable(True)

            row._idx = idx

            self.listbox.append(row)

        self.on_index_changed(player_service, player_service.current_index)

    def on_artist_link_clicked(self, label, uri):
        self.app.navigate_to('artist', artist_id=uri)
        return True

    def on_index_changed(self, service, current_idx):
        child = self.listbox.get_first_child()
        while child:
            if hasattr(child, 'queue_index'):
                if child.queue_index == current_idx:
                    child.add_css_class('active-queue-row')
                else:
                    child.remove_css_class('active-queue-row')
            child = child.get_next_sibling()

        if current_idx >= 0 and current_idx < len(player_service.queue):
            track = player_service.queue[current_idx]
            video_id = track.get('videoId')
            artists = track.get('artists', [])
            artist_id = artists[0].get('id') if artists else None

            if artist_id and artist_id != self.current_similar_artist_id:
                self.current_similar_artist_id = artist_id
                self.load_similar_artists(artist_id)

            if video_id and video_id != getattr(self, 'current_lyrics_video_id', None):
                self.current_lyrics_video_id = video_id
                self.load_lyrics(video_id)

    def on_row_clicked(self, gesture, n_press, x, y, idx):
        player_service.play_index(idx)

    def load_similar_artists(self, artist_id):
        while row := self.similar_listbox.get_first_child():
            self.similar_listbox.remove(row)

        def fetch():
            try:
                artist_data = api.get_artist(artist_id)
                return artist_data.get('related', {}).get('results', [])
            except Exception:
                return []

        def on_loaded(results):
            if not results:
                return

            for artist in results:
                title = artist.get('title', 'Unknown')
                browse_id = artist.get('browseId')

                escaped_title = GLib.markup_escape_text(title)

                row = Adw.ActionRow()
                row.set_title(escaped_title)

                img = Gtk.Image.new_from_icon_name('avatar-default-symbolic')
                img.set_pixel_size(36)
                img.add_css_class('circular')
                row.add_prefix(img)

                thumbnails = artist.get('thumbnails', [])
                thumb_url = thumbnails[-1].get('url') if thumbnails else None
                if thumb_url:
                    load_image_async(thumb_url, img)

                row.set_activatable(True)

                if browse_id:
                    row._browse_id = browse_id

                self.similar_listbox.append(row)

        run_in_background(fetch, on_loaded)

    def load_lyrics(self, video_id):
        self.lyrics_label.set_text('')
        self.lyrics_spinner.start()
        self.lyrics_spinner.set_visible(True)

        def fetch():
            try:
                watch = api.get_watch_playlist(videoId=video_id)
                lyrics_id = watch.get('lyrics')
                if lyrics_id:
                    return api.get_lyrics(lyrics_id)
            except Exception as e:
                logger.warning(f'Error loading lyrics: {e}')
            return None

        def on_loaded(lyrics_data):
            if self.current_lyrics_video_id != video_id:
                return

            self.lyrics_spinner.stop()
            self.lyrics_spinner.set_visible(False)

            if lyrics_data and isinstance(lyrics_data, dict):
                text = lyrics_data.get('lyrics', '')
                source = lyrics_data.get('source', '')

                if text:
                    if source:
                        text += f'\n\n(Fuente: {source})'
                    self.lyrics_label.set_text(text)
                else:
                    self.lyrics_label.set_text('Lyrics not available.')
            else:
                self.lyrics_label.set_text('Lyrics not available.')

        run_in_background(fetch, on_loaded)

    def on_row_activated(self, listbox, row):
        if not hasattr(row, '_idx'):
            return
        idx = row._idx
        player_service.play_queue(player_service.queue, idx)

    def on_similar_activated(self, listbox, row):
        if not hasattr(row, '_browse_id'):
            return
        browse_id = row._browse_id
        self.app.navigate_to('artist', artist_id=browse_id)
