from gi.repository import Adw, GLib, Gtk

from services.image_loader import load_image_async
from services.player_service import player_service
from services.worker import run_in_background
from services.ytmusic import api
from utils.logger import get_logger

logger = get_logger(__name__)


@Gtk.Template(filename='ui/player.ui')
class PlayerView(Gtk.Box):
    __gtype_name__ = 'PlayerView'

    btn_play = Gtk.Template.Child()
    lbl_title = Gtk.Template.Child()
    lbl_artist = Gtk.Template.Child()
    img_cover = Gtk.Template.Child()
    time_label = Gtk.Template.Child()
    timeline_slider = Gtk.Template.Child()
    btn_prev = Gtk.Template.Child()
    btn_next = Gtk.Template.Child()
    btn_shuffle = Gtk.Template.Child()
    btn_repeat = Gtk.Template.Child()
    btn_volume = Gtk.Template.Child()
    scale_volume = Gtk.Template.Child()
    btn_like = Gtk.Template.Child()
    btn_dislike = Gtk.Template.Child()
    img_like = Gtk.Template.Child()
    img_dislike = Gtk.Template.Child()

    def __init__(self, app, **kwargs):
        super().__init__(**kwargs)
        self.app = app

        self.lbl_artist.connect('activate-link', self.on_artist_link_clicked)

        self.current_like_status = 'INDIFFERENT'
        self.current_video_id = None

        self.adj = self.timeline_slider.get_adjustment()
        if not self.adj:
            self.adj = Gtk.Adjustment(value=0, lower=0, upper=100, step_increment=1, page_increment=10)
            self.timeline_slider.set_adjustment(self.adj)
        self.timeline_slider.set_sensitive(False)

        self._is_dragging = False
        self.timeline_slider.connect('change-value', self.on_slider_change_value)

        drag_gesture = Gtk.GestureDrag.new()
        drag_gesture.connect('drag-begin', self.on_slider_drag_begin)
        drag_gesture.connect('drag-end', self.on_slider_drag_end)
        self.timeline_slider.add_controller(drag_gesture)

        vol_adj = Gtk.Adjustment(value=1.0, lower=0.0, upper=1.0, step_increment=0.05, page_increment=0.1)
        self.scale_volume.set_adjustment(vol_adj)

        style_mgr = Adw.StyleManager.get_default()
        style_mgr.connect('notify::dark', self._refresh_thumbs)

        self.last_volume = 1.0
        self.btn_play.set_sensitive(False)
        self.btn_prev.set_sensitive(False)
        self.btn_next.set_sensitive(False)
        self.lbl_title.set_label('')
        self.lbl_artist.set_label('')
        self.time_label.set_label('')
        self.img_cover.set_opacity(0.0)

        self.btn_like.set_visible(False)
        self.btn_dislike.set_visible(False)

        player_service.connect('state-changed', self.on_state_changed)
        player_service.connect('loading-changed', self.on_loading_changed)
        player_service.connect('song-changed', self.on_song_changed)
        player_service.connect('position-changed', self.on_position_changed)
        player_service.connect('volume-changed', self.on_player_volume_changed)
        player_service.connect('seeked', self.on_player_seeked)
        player_service.connect('queue-index-changed', self.update_nav_buttons)
        player_service.connect('queue-changed', self.update_nav_buttons)
        self.btn_prev.set_sensitive(False)
        self.btn_next.set_sensitive(False)



    @Gtk.Template.Callback()
    def on_prev_clicked(self, button):
        player_service.prev_song()

    @Gtk.Template.Callback()
    def on_next_clicked(self, button):
        player_service.next_song()

    @Gtk.Template.Callback()
    def on_shuffle_toggled(self, button):
        player_service.is_shuffle = button.get_active()

    @Gtk.Template.Callback()
    def on_repeat_toggled(self, button):
        player_service.is_repeat = button.get_active()

    @Gtk.Template.Callback()
    def on_volume_changed(self, scale):
        val = scale.get_value()
        self._update_volume_icon(val)
        if abs(player_service.player.get_property('volume') - val) > 0.005:
            player_service.set_volume(val)

    def _update_volume_icon(self, val):
        if val == 0:
            self.btn_volume.set_icon_name('audio-volume-muted-symbolic')
        elif val < 0.33:
            self.btn_volume.set_icon_name('audio-volume-low-symbolic')
        elif val < 0.66:
            self.btn_volume.set_icon_name('audio-volume-medium-symbolic')
        else:
            self.btn_volume.set_icon_name('audio-volume-high-symbolic')

    def on_player_volume_changed(self, service, volume):
        if abs(self.scale_volume.get_value() - volume) > 0.005:
            self.scale_volume.set_value(volume)
        self._update_volume_icon(volume)

    def on_slider_drag_begin(self, gesture, start_x, start_y):
        self._is_dragging = True

    def on_slider_drag_end(self, gesture, offset_x, offset_y):
        self._is_dragging = False
        val = self.adj.get_value()
        player_service.seek(val)

    def on_slider_change_value(self, slider, scroll_type, value):
        if not self._is_dragging:
            player_service.seek(value)
        return False

    def on_player_seeked(self, service, position_sec):
        if not self._is_dragging:
            self.adj.set_value(position_sec)

    @Gtk.Template.Callback()
    def on_like_clicked(self, button):
        if not self.current_video_id:
            return

        new_status = 'INDIFFERENT' if self.current_like_status == 'LIKE' else 'LIKE'
        self._update_rating(new_status)

    @Gtk.Template.Callback()
    def on_dislike_clicked(self, button):
        if not self.current_video_id:
            return

        new_status = 'INDIFFERENT' if self.current_like_status == 'DISLIKE' else 'DISLIKE'
        self._update_rating(new_status)

    def _refresh_thumbs(self, *args):
        is_dark = Adw.StyleManager.get_default().get_dark()
        theme_suffix = '-dark' if is_dark else '-light'

        self.btn_like.remove_css_class('suggested-action')
        self.btn_dislike.remove_css_class('suggested-action')
        self.img_like.set_from_file(f'assets/thumb-like{theme_suffix}.svg')
        self.img_dislike.set_from_file(f'assets/thumb-dislike{theme_suffix}.svg')

        if self.current_like_status == 'LIKE':
            self.btn_like.add_css_class('suggested-action')
            self.img_like.set_from_file(f'assets/thumb-like-filled{theme_suffix}.svg')
        elif self.current_like_status == 'DISLIKE':
            self.btn_dislike.add_css_class('suggested-action')
            self.img_dislike.set_from_file(f'assets/thumb-dislike-filled{theme_suffix}.svg')

    def _update_rating(self, new_status):
        self.current_like_status = new_status
        self._refresh_thumbs()

        idx = player_service.current_index
        if idx >= 0 and idx < len(player_service.queue):
            player_service.queue[idx]['likeStatus'] = new_status

        video_id = self.current_video_id

        def rate():
            try:
                api.rate_song(video_id, new_status)
            except Exception as e:
                logger.error(f'Error rating song: {e}')

        run_in_background(rate, lambda res: None)

    @Gtk.Template.Callback()
    def on_volume_clicked(self, button):
        current_val = self.scale_volume.get_value()
        if current_val == 0:
            restore_val = self.last_volume if self.last_volume > 0 else 1.0
            self.scale_volume.set_value(restore_val)
        else:
            self.last_volume = current_val
            self.scale_volume.set_value(0.0)

    def update_nav_buttons(self, service, *args):
        idx = service.current_index
        q_len = len(service.queue)

        # If repeat is enabled, prev/next are always enabled if there are songs
        if service.is_repeat and q_len > 0:
            self.btn_prev.set_sensitive(True)
            self.btn_next.set_sensitive(True)
        else:
            # If shuffle is enabled, prev works normally and next works as long as there is > 1 song
            if service.is_shuffle and q_len > 1:
                self.btn_prev.set_sensitive(True)
                self.btn_next.set_sensitive(True)
            else:
                self.btn_prev.set_sensitive(idx > 0)
                self.btn_next.set_sensitive(idx >= 0 and idx < q_len - 1)

    @Gtk.Template.Callback()
    def on_play_clicked(self, button):
        player_service.toggle_play()

    def on_state_changed(self, service, is_playing):
        if is_playing:
            self.btn_play.set_icon_name('media-playback-pause-symbolic')
            self.btn_play.set_tooltip_text('Pause')
        else:
            self.btn_play.set_icon_name('media-playback-start-symbolic')
            self.btn_play.set_tooltip_text('Play')

    def on_loading_changed(self, service, is_loading):
        if is_loading:
            spinner = Gtk.Spinner()
            spinner.start()
            self.btn_play.set_child(spinner)
            self.btn_play.set_tooltip_text('Loading...')
        else:
            self.on_state_changed(service, service.is_playing)

    def on_artist_link_clicked(self, label, uri):
        if uri.startswith('album:'):
            album_id = uri.split(':', 1)[1]
            self.app.navigate_to('album', album_id=album_id)
        else:
            self.app.navigate_to('artist', artist_id=uri)
        return True

    def on_song_changed(self, service, title, artist, thumb_url):
        self.btn_play.set_sensitive(True)
        self.timeline_slider.set_sensitive(True)
        self.adj.set_value(0)
        self.lbl_title.set_label(title)
        self.img_cover.set_opacity(1.0)

        self.btn_like.set_visible(True)
        self.btn_dislike.set_visible(True)

        idx = player_service.current_index
        artist_id = None

        self.current_video_id = None
        self.current_like_status = 'INDIFFERENT'
        self._refresh_thumbs()

        if idx >= 0 and idx < len(player_service.queue):
            track = player_service.queue[idx]
            artists = track.get('artists', [])
            artist_id = artists[0].get('id') if artists else None
            self.current_video_id = track.get('videoId')
            self.current_like_status = track.get('likeStatus', 'INDIFFERENT')

            self._refresh_thumbs()

            if self.current_video_id:
                vid = self.current_video_id

                def fetch_status():
                    try:
                        watch = api.get_watch_playlist(videoId=vid)
                        tracks = watch.get('tracks', [])
                        for t in tracks:
                            if t.get('videoId') == vid and 'likeStatus' in t:
                                return t.get('likeStatus')
                    except Exception:
                        pass
                    return None

                def on_status_loaded(status):
                    if status and self.current_video_id == vid:
                        self.current_like_status = status
                        self._refresh_thumbs()

                        idx = player_service.current_index
                        if idx >= 0 and idx < len(player_service.queue):
                            if player_service.queue[idx].get('videoId') == vid:
                                player_service.queue[idx]['likeStatus'] = status

                run_in_background(fetch_status, on_status_loaded)

        if artist_id:
            escaped_artist = GLib.markup_escape_text(artist)
            markup = f"<a href='{artist_id}' title='Go to artist'>{escaped_artist}</a>"
        else:
            markup = GLib.markup_escape_text(artist)

        if idx >= 0 and idx < len(player_service.queue):
            track = player_service.queue[idx]
            album = track.get('album', {})
            if album and album.get('name'):
                escaped_album = GLib.markup_escape_text(album.get('name'))
                album_id = album.get('id') or album.get('browseId')
                if album_id:
                    markup += f" • <a href='album:{album_id}' title='Go to album'>{escaped_album}</a>"
                else:
                    markup += f' • {escaped_album}'

                year = track.get('year') or album.get('year')
                if year:
                    markup += f' ({year})'

        self.lbl_artist.set_markup(markup)

        if thumb_url:
            load_image_async(thumb_url, self.img_cover, max_size=60)
        else:
            self.img_cover.set_from_icon_name('audio-x-generic-symbolic')

    def on_position_changed(self, service, position, duration):
        def format_time(seconds):
            m = seconds // 60
            s = seconds % 60
            return f'{m}:{s:02d}'

        if not self._is_dragging:
            self.time_label.set_label(f'{format_time(position)} / {format_time(duration)}')

            if duration > 0:
                if self.adj.get_upper() != duration:
                    self.adj.set_upper(duration)

                self.adj.set_value(position)
