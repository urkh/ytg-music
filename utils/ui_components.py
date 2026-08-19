from gi.repository import Adw, GLib, Gtk, Pango

from models.media import MediaItem
from services.image_loader import load_image_async
from services.player_service import player_service
from services.worker import run_in_background
from services.ytmusic import api
from utils.logger import get_logger

logger = get_logger(__name__)


def create_item_card(app, item: MediaItem) -> Gtk.Box:
    """Creates a generic visual card for Albums, Artists, Playlists, Songs, or Videos"""
    if not item.resultType:
        return None

    box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
    box.set_size_request(160, 220)
    box.set_halign(Gtk.Align.CENTER)
    box.set_valign(Gtk.Align.START)

    img = Gtk.Image.new_from_icon_name('audio-x-generic-symbolic')
    img.set_pixel_size(160)

    if item.resultType == 'artist':
        img.add_css_class('circular')

    box.append(img)

    thumb_url = item.best_thumbnail_url
    if thumb_url:
        load_image_async(thumb_url, img, max_size=200)

    vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)

    title_lbl = Gtk.Label(label=item.display_title)
    title_lbl.add_css_class('heading')
    title_lbl.set_wrap(True)
    title_lbl.set_wrap_mode(Pango.WrapMode.WORD_CHAR)
    title_lbl.set_lines(2)
    title_lbl.set_ellipsize(Pango.EllipsizeMode.END)
    title_lbl.set_width_chars(14)
    title_lbl.set_max_width_chars(14)
    title_lbl.set_halign(Gtk.Align.FILL)
    title_lbl.set_xalign(0.0)
    vbox.append(title_lbl)

    subtitle_lbl = Gtk.Label(label=item.display_subtitle)
    subtitle_lbl.add_css_class('dim-label')
    subtitle_lbl.set_wrap(True)
    subtitle_lbl.set_wrap_mode(Pango.WrapMode.WORD_CHAR)
    subtitle_lbl.set_lines(2)
    subtitle_lbl.set_ellipsize(Pango.EllipsizeMode.END)
    subtitle_lbl.set_width_chars(18)
    subtitle_lbl.set_max_width_chars(18)
    subtitle_lbl.set_halign(Gtk.Align.FILL)
    subtitle_lbl.set_xalign(0.0)
    vbox.append(subtitle_lbl)

    box.append(vbox)

    box._item = item
    return box


def on_card_clicked(app, item: MediaItem):
    """Global handler for cards. navigates to the corresponding view"""

    result_type = item.resultType

    if result_type == 'artist':
        artist_id = item.browseId
        if not artist_id and item.artists and isinstance(item.artists, list):
            artist_id = item.artists[0].get('id')
        if artist_id:
            app.navigate_to('artist', artist_id=artist_id)

    elif result_type == 'album':
        if item.browseId:
            app.navigate_to('album', album_id=item.browseId)

    elif result_type == 'playlist':
        playlist_id = item.playlistId or item.browseId
        if not playlist_id:
            return

        def load_and_play():
            try:
                data = api.get_playlist(playlist_id, limit=100)
                return data.get('tracks', [])
            except Exception as e:
                logger.error(f'Error loading playlist: {e}')
                return []

        def on_loaded(tracks):
            if tracks:
                player_service.play_queue(tracks, 0)

        run_in_background(load_and_play, on_loaded)

    elif result_type in ('song', 'video'):
        track = item.to_queue_track()
        if track:
            player_service.play_queue([track], 0)


def create_song_row(item: MediaItem) -> Adw.ActionRow:
    """Creates a standardized list row for a song"""
    escaped_title = GLib.markup_escape_text(item.title)

    row = Adw.ActionRow()
    row.set_title(escaped_title)

    img = Gtk.Image.new_from_icon_name('audio-x-generic-symbolic')
    img.set_pixel_size(48)
    img.set_valign(Gtk.Align.CENTER)

    thumb_url = item.best_thumbnail_url
    if thumb_url:
        load_image_async(thumb_url, img, max_size=60)

    row.add_prefix(img)

    album_name = item.album.get('name') if isinstance(item.album, dict) else ''
    if album_name:
        escaped_album = GLib.markup_escape_text(album_name)
        row.set_subtitle(escaped_album)

    row.set_activatable(True)

    row._img_cover = img
    row._item = item
    row.video_id = item.videoId

    return row


def update_song_row(row: Adw.ActionRow, item: MediaItem) -> None:
    """Updates the visual data of an existing Adw.ActionRow to avoid creating and destroying widgets"""
    title = item.title
    escaped_title = GLib.markup_escape_text(title)
    row.set_title(escaped_title)

    album_name = item.album.get('name') if isinstance(item.album, dict) else ''
    escaped_album = GLib.markup_escape_text(album_name) if album_name else ''
    row.set_subtitle(escaped_album)

    # Explicitly discard old texture to help free GPU/GDK RAM
    row._img_cover.clear()

    thumb_url = item.best_thumbnail_url
    if thumb_url:
        load_image_async(thumb_url, row._img_cover, max_size=60)
    else:
        row._img_cover.set_from_icon_name('audio-x-generic-symbolic')

    row._item = item
    row.video_id = item.videoId


def update_active_list_row(list_widget, current_video_id: str):
    """
    Iterates over the children of a container widget and updates 
    the CSS class `active-queue-row` on the row matching the current video
    """
    if not list_widget:
        return

    child = list_widget.get_first_child()
    while child:
        if hasattr(child, 'video_id'):
            if child.video_id == current_video_id:
                child.add_css_class('active-queue-row')
            else:
                child.remove_css_class('active-queue-row')
        child = child.get_next_sibling()


def create_error_page() -> Adw.StatusPage:
    """Creates a generic and minimalist error screen"""
    status = Adw.StatusPage()
    status.set_icon_name('network-error-symbolic')
    return status


def show_error_page(view, content_widget=None):
    """
    Hides the main content and shows a standardized error screen.
    Uses Gtk.Overlay to overlay the error without destroying the UI structure.
    """
    if content_widget:
        content_widget.set_visible(False)

    if not hasattr(view, 'error_status_page'):
        view.error_status_page = create_error_page()
        view.add_overlay(view.error_status_page)

    view.error_status_page.set_visible(True)


def hide_error_page(view, content_widget=None):
    """Hides the error screen and shows the main content again"""
    if hasattr(view, 'error_status_page'):
        view.error_status_page.set_visible(False)

    if content_widget:
        content_widget.set_visible(True)
