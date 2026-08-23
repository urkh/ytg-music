from concurrent.futures import ThreadPoolExecutor

import pytest

from services import image_loader, worker, ytmusic
from services.mpris import MPRISService
from services.player_service import player_service


@pytest.mark.vcr()
def test_api_get_home():
    """
    Tests that the API can get 'home' anonymously.
    The first time it will go to the internet, then it will use cassettes/test_api_get_home.yaml.
    """
    # Since we have force_anonymous_mode, api.auth will be None
    ytmusic.reload_api()
    home_data = ytmusic.api.get_home()

    # Verify that it brings sections (mixes, recommended, etc)
    assert isinstance(home_data, list)
    assert len(home_data) > 0

    # Each section has a title and contents
    assert 'title' in home_data[0]
    assert 'contents' in home_data[0]


@pytest.mark.vcr()
def test_api_get_explore():
    """
    Tests the 'Explore' tab (Trending, New releases).
    """
    ytmusic.reload_api()
    explore_data = ytmusic.api.get_explore()

    # It should be a dictionary with several categories
    assert isinstance(explore_data, dict)
    assert len(explore_data) > 0

    # Verify that it has some of the classic keys
    keys = list(explore_data.keys())
    assert any(k in keys for k in ['new_releases', 'top_songs', 'trending'])


def test_image_loader_disk_only_no_ram():
    # Verify that there is no LRU storage in RAM
    assert not hasattr(image_loader, '_image_cache')
    assert not hasattr(image_loader, 'MAX_CACHE_SIZE')

    # Verify disk cache path
    url = 'https://example.com/test_image.jpg'
    path = image_loader.get_disk_cache_path(url)
    assert path.endswith('.img')
    assert 'thumbnails' in path

    # Verify bounded thread pool for image loader
    assert isinstance(image_loader._image_executor, ThreadPoolExecutor)
    assert image_loader._image_executor._max_workers == 4


def test_round_pixbuf():
    from gi.repository import GdkPixbuf

    # Test round_pixbuf on landscape pixbuf (300x100)
    pb = GdkPixbuf.Pixbuf.new(GdkPixbuf.Colorspace.RGB, True, 8, 300, 100)
    rounded = image_loader.round_pixbuf(pb, radius=16)
    assert rounded.get_width() == 300
    assert rounded.get_height() == 100

    # Test round_pixbuf with radius larger than dimensions (should clamp safely)
    pb_small = GdkPixbuf.Pixbuf.new(GdkPixbuf.Colorspace.RGB, True, 8, 20, 10)
    rounded_small = image_loader.round_pixbuf(pb_small, radius=50)
    assert rounded_small.get_width() == 20
    assert rounded_small.get_height() == 10


def test_best_thumbnail_selection():
    from models.media import AlbumDetail, ArtistDetail, MediaItem, get_best_thumbnail_url

    thumbnails = [
        {'url': 'https://example.com/small.jpg', 'width': 540, 'height': 225},
        {'url': 'https://example.com/huge.jpg', 'width': 2880, 'height': 1200},
        {'url': 'https://example.com/medium.jpg', 'width': 816, 'height': 340},
    ]

    assert get_best_thumbnail_url(thumbnails) == 'https://example.com/huge.jpg'

    artist = ArtistDetail(name='Test Artist', thumbnails=thumbnails)
    assert artist.best_thumbnail_url == 'https://example.com/huge.jpg'

    album = AlbumDetail(title='Test Album', thumbnails=thumbnails)
    assert album.best_thumbnail_url == 'https://example.com/huge.jpg'

    media = MediaItem(title='Test Song', thumbnails=thumbnails)
    assert media.best_thumbnail_url == 'https://example.com/huge.jpg'

    # Empty / None handling
    assert get_best_thumbnail_url([]) is None
    assert get_best_thumbnail_url(None) is None


def test_load_image_async_preserves_aspect_ratio(mocker):
    import time

    from gi.repository import GdkPixbuf, GLib, Gtk

    pb = GdkPixbuf.Pixbuf.new(GdkPixbuf.Colorspace.RGB, False, 8, 2400, 1000)
    success, buffer = pb.save_to_bufferv('png', [], [])
    mock_resp = mocker.MagicMock()
    mock_resp.status_code = 200
    mock_resp.content = bytes(buffer)

    mocker.patch('services.image_loader.requests.get', return_value=mock_resp)

    pic = Gtk.Picture()
    image_loader.load_image_async('https://fake.url/test_landscape.png', pic, is_unrounded=True, max_size=1200)

    ctx = GLib.MainContext.default()
    for _ in range(50):
        ctx.iteration(False)
        if pic.get_paintable() is not None:
            break
        time.sleep(0.02)

    paintable = pic.get_paintable()
    assert paintable is not None
    assert paintable.get_intrinsic_width() == 1200
    assert paintable.get_intrinsic_height() == 500


def test_worker_bounded_thread_pool():
    # Verify bounded thread pool for general worker tasks
    assert isinstance(worker._executor, ThreadPoolExecutor)
    assert worker._executor._max_workers == 4


def test_player_service_seek_and_volume():
    events = []
    player_service.connect('volume-changed', lambda s, v: events.append(('volume', v)))
    player_service.connect('seeked', lambda s, pos: events.append(('seeked', pos)))

    player_service.set_volume(0.65)
    assert player_service.player.get_property('volume') == pytest.approx(0.65)
    assert ('volume', 0.65) in events

    player_service.current_video_id = 'test_123'
    player_service.seek(42)
    assert player_service.current_position == 42
    assert ('seeked', 42) in events


def test_mpris_service_properties_and_methods(mocker):
    mock_app = mocker.MagicMock()
    mock_app.win = mocker.MagicMock()

    mpris = MPRISService(mock_app)

    # Test Root property handlers
    identity = mpris._handle_root_get_prop(None, '', '', '', 'Identity')
    assert identity.unpack() == 'YTG Music'

    can_quit = mpris._handle_root_get_prop(None, '', '', '', 'CanQuit')
    assert can_quit.unpack() is True

    # Test Player property handlers
    player_service.is_playing = True
    player_service.current_video_id = 'abc'
    status = mpris._handle_player_get_prop(None, '', '', '', 'PlaybackStatus')
    assert status.unpack() == 'Playing'

    player_service.queue = [
        {'videoId': 'abc', 'title': 'Test Song', 'artists': [{'name': 'Test Artist'}], 'thumbnails': []}
    ]
    player_service.current_index = 0
    player_service.current_duration = 180

    meta = mpris._handle_player_get_prop(None, '', '', '', 'Metadata')
    meta_dict = meta.unpack()
    assert meta_dict['xesam:title'] == 'Test Song'
    assert meta_dict['xesam:artist'] == ['Test Artist']
    assert meta_dict['mpris:length'] == 180 * 1_000_000

    # Test Player method handlers
    mock_invocation = mocker.MagicMock()
    mpris._handle_player_method_call(None, '', '', '', 'PlayPause', None, mock_invocation)
    mock_invocation.return_value.assert_called_once()
