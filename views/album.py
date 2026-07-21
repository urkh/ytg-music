from gi.repository import Adw, GLib, Gtk

from models.media import AlbumDetail
from services.image_loader import load_image_async
from services.player_service import player_service
from services.worker import run_in_background
from services.ytmusic import api
from utils.formatters import format_description
from utils.memory import free_memory
from utils.ui_components import hide_error_page, show_error_page, update_active_list_row


@Gtk.Template(filename='ui/album.ui')
class AlbumView(Gtk.Overlay):
    __gtype_name__ = 'AlbumView'

    content_box = Gtk.Template.Child()
    img_cover = Gtk.Template.Child()
    lbl_album_title = Gtk.Template.Child()
    lbl_album_metadata = Gtk.Template.Child()
    lbl_description = Gtk.Template.Child()
    btn_toggle_desc = Gtk.Template.Child()
    list_tracks = Gtk.Template.Child()
    spinner = Gtk.Template.Child()
    btn_play_album = Gtk.Template.Child()

    def __init__(self, app, **kwargs):
        super().__init__(**kwargs)
        self.app = app

        self.current_album_id = None
        self.album_detail = None

        self.lbl_album_metadata.connect('activate-link', self.on_artist_link_clicked)
        player_service.connect('song-changed', self.on_song_changed)
        self.btn_play_album.connect('clicked', self.on_play_album_clicked)
        self.btn_toggle_desc.connect('toggled', self.on_toggle_album_description)
        self.list_tracks.connect('row-activated', self.on_track_activated)

    def load_album(self, album_id):
        if self.current_album_id == album_id:
            return

        self.clear_view()
        self.current_album_id = album_id
        self.spinner.start()
        self.spinner.set_visible(True)

        def fetch():
            return api.get_album(album_id)

        run_in_background(fetch, self.on_album_loaded)

    def on_toggle_album_description(self, button):
        self._set_description()

    def on_play_album_clicked(self, button):
        if not self.album_detail:
            return

        queue = self.album_detail.get_queue_tracks(self.current_album_id)

        if queue:
            player_service.play_queue(queue, 0)

    def on_artist_link_clicked(self, label, uri):
        self.app.navigate_to('artist', artist_id=uri)
        return True

    def on_song_changed(self, service, title, artist, thumb_url):
        self._update_active_row()

    def on_album_loaded(self, data):
        self.spinner.stop()
        self.spinner.set_visible(False)

        if not data:
            show_error_page(self, self.content_box)
            return

        hide_error_page(self, self.content_box)
        detail = AlbumDetail.model_validate(data)

        self.album_detail = detail
        self.lbl_album_title.set_label(detail.title)
        self.raw_full_desc = detail.description or ''

        self._set_metadata(detail)
        self._set_description()
        self._set_cover_image(detail.best_thumbnail_url)

        self._render_tracks(detail.tracks)

        free_memory()

    def on_track_activated(self, listbox, row):
        if not self.album_detail or not hasattr(row, '_item'):
            return

        queue = self.album_detail.get_queue_tracks(self.current_album_id)
        clicked_idx = row.get_index()

        if queue and 0 <= clicked_idx < len(queue):
            player_service.play_queue(queue, clicked_idx)

    def _update_active_row(self):
        update_active_list_row(self.list_tracks, player_service.current_video_id)

    def _set_metadata(self, detail: AlbumDetail):
        meta = []
        if detail.artist_name:
            escaped_artist = GLib.markup_escape_text(detail.artist_name)
            if detail.artist_id:
                meta.append(f'<a href="{detail.artist_id}" title="Go to artist">{escaped_artist}</a>')
            else:
                meta.append(escaped_artist)

        if detail.year:
            meta.append(str(detail.year))
        if detail.trackCount:
            meta.append(f'{detail.trackCount} canciones')

        self.lbl_album_metadata.set_markup(' • '.join(meta))

    def _set_description(self):
        desc = self.raw_full_desc
        is_long = len(desc) > 150
        self.btn_toggle_desc.set_visible(is_long)

        if is_long and not self.btn_toggle_desc.get_active():
            desc = f'{desc[:150].strip()}...'
            self.btn_toggle_desc.set_label('Show more')
        elif is_long:
            self.btn_toggle_desc.set_label('Show less')

        self.lbl_description.set_markup(format_description(desc))

    def _set_cover_image(self, url: str):
        self.img_cover.clear()
        if url:
            load_image_async(url, self.img_cover)

    def _render_tracks(self, tracks: list):
        self.btn_play_album.set_sensitive(bool(tracks))

        while child := self.list_tracks.get_first_child():
            self.list_tracks.remove(child)

        for track in tracks:
            self.add_track_row(track)

        self._update_active_row()

    def add_track_row(self, track):
        row = Adw.ActionRow()

        title = track.get('title', 'Unknown')
        row.set_title(GLib.markup_escape_text(title))

        track_num = track.get('trackNumber', '')
        num_lbl = Gtk.Label(label=str(track_num) if track_num else '')
        num_lbl.set_valign(Gtk.Align.CENTER)
        num_lbl.add_css_class('dim-label')
        num_lbl.set_width_chars(3)
        num_lbl.set_halign(Gtk.Align.END)
        row.add_prefix(num_lbl)

        duration = track.get('duration', '')
        dur_lbl = Gtk.Label(label=duration if duration else '')
        dur_lbl.set_valign(Gtk.Align.CENTER)
        dur_lbl.add_css_class('dim-label')
        row.add_suffix(dur_lbl)

        row.set_activatable(True)
        row._item = track
        row.video_id = track.get('videoId')

        self.list_tracks.append(row)

    def clear_view(self):
        self.content_box.set_visible(False)
        self.album_detail = None
