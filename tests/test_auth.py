import json
import logging
import os

from services import ytmusic


def test_anonymous_initialization(caplog):
    """
    Ensures that if there is no headers file the API is initialized in anonymous mode
    """
    with caplog.at_level(logging.INFO):
        ytmusic.reload_api()

    assert 'YTMusic initialized anonymously' in caplog.text

    # Verify that the API has been instantiated
    assert ytmusic.api is not None


def test_authenticated_initialization(mocker, tmp_path, caplog):
    """
    Simulates the presence of a real headers_auth.json file to ensure that the system attempts to authenticate
    """
    fake_headers_path = tmp_path / 'headers_auth.json'
    fake_headers = {
        'User-Agent': 'Mozilla/5.0',
        'Accept': '*/*',
        'Accept-Language': 'en-US,en;q=0.5',
        'Content-Type': 'application/json',
        'X-Goog-AuthUser': '0',
        'x-origin': 'https://music.youtube.com',
        'Cookie': 'fake_cookie=123; __Secure-3PAPISID=dummy_value',
        'Authorization': 'SAPISIDHASH 12345',
    }
    fake_headers_path.write_text(json.dumps(fake_headers))

    mocker.patch('services.ytmusic.get_auth_file_path', return_value=str(fake_headers_path))

    # IMPORTANT: We disable the anonymous mock we set in conftest.py specifically for this test
    # by intercepting os.path.exists again but in a controlled way
    original_exists = os.path.exists

    def local_mocked_exists(path):
        if 'headers_auth.json' in str(path):
            return True
        return original_exists(path)

    mocker.patch('os.path.exists', side_effect=local_mocked_exists)

    # When calling reload_api, it should use our fake file
    with caplog.at_level(logging.INFO):
        ytmusic.reload_api()

    assert 'YTMusic initialized with Cookies' in caplog.text
    assert ytmusic.api is not None
