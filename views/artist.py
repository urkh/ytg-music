from gi.repository import Gtk

from models.media import ArtistDetail, parse_media_item
from services.image_loader import load_image_async
from services.player_service import player_service
from services.worker import run_in_background
from services.ytmusic import api
from utils.formatters import format_description
from utils.ui_components import (
    create_item_card,
    create_song_row,
    hide_error_page,
    on_card_clicked,
    show_error_page,
    update_active_list_row,
)


@Gtk.Template(filename='ui/artist.ui')
class ArtistView(Gtk.Overlay):
    __gtype_name__ = 'ArtistView'

    content_box = Gtk.Template.Child()
    img_cover = Gtk.Template.Child()
    lbl_artist_name = Gtk.Template.Child()
    lbl_subscribers = Gtk.Template.Child()
    lbl_description = Gtk.Template.Child()
    btn_toggle_description = Gtk.Template.Child()
    btn_subscribe = Gtk.Template.Child()
    spinner = Gtk.Template.Child()
    list_top_songs = Gtk.Template.Child()
    flow_albums = Gtk.Template.Child()

    def __init__(self, app, **kwargs):
        super().__init__(**kwargs)
        self.app = app
        self.current_artist_id = None
        self.is_subscribed = False

        player_service.connect('song-changed', self.on_song_changed)
        self.btn_subscribe.connect('clicked', self.on_subscribe_clicked)
        self.btn_toggle_description.connect('toggled', self.on_toggle_artist_description)

        self.list_top_songs.connect('row-activated', self.on_song_activated)
        self.flow_albums.connect('child-activated', self.on_album_activated)

    def load_artist(self, artist_id):
        if self.current_artist_id == artist_id:
            return

        self.clear_view()
        self.current_artist_id = artist_id
        self.content_box.set_visible(False)
        self.spinner.start()
        self.spinner.set_visible(True)

        def fetch():
            return api.get_artist(artist_id)

        run_in_background(fetch, self.on_artist_loaded)

    def on_subscribe_clicked(self, button):
        if not self.current_artist_id:
            return

        self.is_subscribed = not self.is_subscribed
        self._set_subscribe_btn()

        artist_id = self.current_artist_id
        is_sub = self.is_subscribed

        def toggle_sub():
            if is_sub:
                api.subscribe_artists([artist_id])
            else:
                api.unsubscribe_artists([artist_id])

        run_in_background(toggle_sub)

    def on_toggle_artist_description(self, button):
        self._set_description()

    def on_song_changed(self, service, title, artist, thumb_url):
        self._update_active_row()

    def on_artist_loaded(self, data):
        self.spinner.stop()
        self.spinner.set_visible(False)

        if not data:
            show_error_page(self, self.content_box)
            return

        hide_error_page(self, self.content_box)
        detail = ArtistDetail.model_validate(data)

        self.lbl_artist_name.set_label(detail.name)
        self.lbl_subscribers.set_label(detail.display_subscribers)
        self.raw_full_desc = detail.description or ''
        self.is_subscribed = detail.subscribed
        self.btn_subscribe.set_visible(True)

        self._set_subscribe_btn()
        self._set_description()
        self._set_cover_image(detail.best_thumbnail_url)

        self._render_songs(detail.songs)
        self._render_albums(detail.albums)

    def on_song_activated(self, listbox, row):
        if not hasattr(row, '_item'):
            return

        fallback_artist = {
            'name': self.lbl_artist_name.get_label(),
            'id': self.current_artist_id,
        }
        queue = [item.to_queue_track(fallback_artist) for item in self.song_items if item.videoId]

        if not queue:
            return

        clicked_idx = row.get_index()
        if not (0 <= clicked_idx < len(queue)):
            clicked_idx = 0

        player_service.play_queue(queue, clicked_idx)

        browse_id = self.songs_data.get('browseId')
        if browse_id:
            self._fetch_more_songs(browse_id, len(queue), fallback_artist)

    def _fetch_more_songs(self, browse_id: str, skip_count: int, fallback_artist: dict):
        def fetch_more():
            return api.get_playlist(browse_id)

        def on_more_loaded(playlist):
            if not playlist or 'tracks' not in playlist:
                return

            new_tracks = playlist['tracks'][skip_count:]
            if not new_tracks:
                return

            more_queue = []
            for song_dict in new_tracks:
                item = parse_media_item(song_dict, force_type='song')
                if not item.videoId:
                    continue

                more_queue.append(item.to_queue_track(fallback_artist))

            if more_queue:
                player_service.append_to_queue(more_queue)

        run_in_background(fetch_more, on_more_loaded)

    def _set_subscribe_btn(self):
        if self.is_subscribed:
            self.btn_subscribe.set_label('Subscribed')
            self.btn_subscribe.remove_css_class('suggested-action')
        else:
            self.btn_subscribe.set_label('Subscribe')
            self.btn_subscribe.add_css_class('suggested-action')

    def _set_description(self):
        desc = self.raw_full_desc
        is_long = len(desc) > 150
        self.btn_toggle_description.set_visible(is_long)

        if is_long and not self.btn_toggle_description.get_active():
            desc = f'{desc[:150].strip()}...'
            self.btn_toggle_description.set_label('Show more')
        elif is_long:
            self.btn_toggle_description.set_label('Show less')

        self.lbl_description.set_markup(format_description(desc))

    def _set_cover_image(self, url: str):
        self.img_cover.set_paintable(None)
        if url:
            load_image_async(url, self.img_cover, is_unrounded=True, max_size=1920)

    def _render_songs(self, songs: dict):
        self.songs_data = songs
        results = songs.get('results', [])
        self.song_items = [parse_media_item(song, force_type='song') for song in results]

        while child := self.list_top_songs.get_first_child():
            self.list_top_songs.remove(child)

        for item in self.song_items:
            row = create_song_row(item)
            self.list_top_songs.append(row)

        self._update_active_row()

    def _render_albums(self, albums: dict):
        results = albums.get('results', [])

        while child := self.flow_albums.get_first_child():
            self.flow_albums.remove(child)

        for album in results:
            parsed = parse_media_item(album, force_type='album')
            card = create_item_card(self.app, parsed)
            if card:
                self.flow_albums.append(card)

    def on_album_activated(self, flowbox, child):
        box = child.get_child()
        if not hasattr(box, '_item'):
            return

        on_card_clicked(self.app, box._item)

    def _update_active_row(self):
        update_active_list_row(self.list_top_songs, player_service.current_video_id)

    def clear_view(self):
        self.img_cover.set_paintable(None)
        self.content_box.set_visible(False)
        self.song_items = []
        self.songs_data = {}
