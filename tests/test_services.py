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
