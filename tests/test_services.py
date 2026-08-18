import pytest

from services import ytmusic


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
    import services.image_loader as image_loader

    # Verify that there is no LRU storage in RAM
    assert not hasattr(image_loader, '_image_cache')
    assert not hasattr(image_loader, 'MAX_CACHE_SIZE')

    # Verify disk cache path
    url = 'https://example.com/test_image.jpg'
    path = image_loader.get_disk_cache_path(url)
    assert path.endswith('.img')
    assert 'thumbnails' in path


def test_player_service_seek_and_volume():
    from services.player_service import player_service

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
    from services.mpris import MPRISService
    from services.player_service import player_service

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

