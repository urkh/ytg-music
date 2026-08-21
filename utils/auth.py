import json
import os
import tempfile
import time
import uuid

import browsercookie
from gi.repository import GLib
from ytmusicapi import YTMusic
from ytmusicapi.auth.oauth import OAuthCredentials
from ytmusicapi.ytmusic import get_authorization, sapisid_from_cookie

from utils.logger import get_logger

logger = get_logger(__name__)

OAUTH_CLIENT_ID = ''
OAUTH_CLIENT_SECRET = ''


def get_auth_file_path() -> str:
    """Returns the XDG Base Directory for saving session"""
    data_dir = os.path.join(GLib.get_user_data_dir(), 'ytg-music')
    os.makedirs(data_dir, exist_ok=True)
    target_path = os.path.join(data_dir, 'headers_auth.json')
    return target_path


def get_oauth_file_path() -> str:
    """Returns the XDG Base Directory for saving OAuth session"""
    data_dir = os.path.join(GLib.get_user_data_dir(), 'ytg-music')
    os.makedirs(data_dir, exist_ok=True)
    return os.path.join(data_dir, 'oauth.json')


def get_oauth_credentials() -> OAuthCredentials:
    """Instantiate OAuthCredentials using the configured ID and secret"""
    return OAuthCredentials(OAUTH_CLIENT_ID, OAUTH_CLIENT_SECRET)


def extract_browser_cookies() -> str:
    """Extracts and filters essential YouTube cookies from local browsers (Firefox, Chrome, Chromium, Brave, etc.)"""
    essential_keys = [
        '__Secure-1PSID',
        '__Secure-3PSID',
        '__Secure-1PAPISID',
        '__Secure-3PAPISID',
        '__Secure-1PSIDTS',
        '__Secure-3PSIDTS',
        'LOGIN_INFO',
        'SAPISID',
        'APISID',
        'HSID',
        'SSID',
        'YSC',
        'PREF',
        'VISITOR_INFO1_LIVE',
    ]

    browser_loaders = [
        ('Firefox', browsercookie.firefox),
        ('Chrome', browsercookie.chrome),
        ('Chromium', browsercookie.chromium),
        ('Brave', browsercookie.brave),
        ('Edge', browsercookie.edge),
        ('Vivaldi', browsercookie.vivaldi),
    ]

    for name, loader in browser_loaders:
        try:
            cj = loader()
            filtered = [f'{c.name}={c.value}' for c in cj if 'youtube.com' in c.domain and c.name in essential_keys]
            if filtered:
                logger.info(f'Successfully extracted YouTube cookies from {name}')
                return '; '.join(filtered)
        except Exception as e:
            logger.debug(f'Could not load cookies from {name}: {e}')

    raise Exception(
        'Error: The browser cookies are not present or are expired. Please, log in to YouTube Music and try again.'
    )


def build_base_headers(cookie_str: str) -> dict:
    """Builds base HTTP headers including dynamic SAPISIDHASH authorization"""
    headers = {
        'Accept': '*/*',
        'Content-Type': 'application/json',
        'x-origin': 'https://music.youtube.com',
        'Cookie': cookie_str,
    }
    try:
        sapisid = sapisid_from_cookie(cookie_str)
        headers['Authorization'] = get_authorization(sapisid + ' ' + headers['x-origin'])
    except Exception as e:
        logger.warning(f'Could not generate SAPISIDHASH: {e}')

    return headers


def find_valid_accounts(base_headers: dict) -> list:
    """Scans account profiles looking for valid YouTube Music channels"""
    valid_accounts = []

    for i in range(6):
        headers = base_headers.copy()
        headers['X-Goog-AuthUser'] = str(i)
        tmp_path = os.path.join(tempfile.gettempdir(), f'ytm_{uuid.uuid4().hex}.json')

        try:
            with open(tmp_path, 'w') as f:
                json.dump(headers, f)

            test_api = YTMusic(tmp_path)
            info = test_api.get_account_info()
            if info and 'accountName' in info:
                valid_accounts.append(
                    {
                        'auth_user': str(i),
                        'name': info['accountName'],
                        'handle': info.get('channelHandle', f'Profile {i}'),
                        'photo_url': info.get('accountPhotoUrl'),
                        'headers': headers,
                    }
                )
        except Exception:
            pass
        finally:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)

    if not valid_accounts:
        raise Exception('Error: No valid YouTube Music channels were found or an authentication error occurred.')

    return valid_accounts


def start_oauth_flow() -> dict:
    """Initiates the OAuth device flow and returns code info"""
    creds = get_oauth_credentials()
    code_info = creds.get_code()
    # returns dict with: device_code, user_code, verification_url, expires_in, interval
    return code_info


def poll_oauth_token(device_code: str) -> dict:
    """Attempts to get the token. Returns the token dict if successful, or an error dict if pending"""
    creds = get_oauth_credentials()
    raw_token = creds.token_from_code(device_code)
    return raw_token


def is_authenticated() -> bool:
    """Checks if either an OAuth session or headers session exists"""
    return os.path.exists(get_oauth_file_path()) or os.path.exists(get_auth_file_path())


def save_oauth_token(raw_token: dict) -> None:
    """Saves the raw token to oauth.json in the format expected by ytmusicapi"""
    token_dict = {
        'access_token': raw_token['access_token'],
        'refresh_token': raw_token['refresh_token'],
        'scope': raw_token.get('scope', 'https://www.googleapis.com/auth/youtube'),
        'token_type': raw_token.get('token_type', 'Bearer'),
        'expires_in': raw_token.get('expires_in', 3600),
        'expires_at': int(time.time()) + raw_token.get('expires_in', 3600),
    }
    target_path = get_oauth_file_path()
    with open(target_path, 'w', encoding='utf-8') as f:
        json.dump(token_dict, f, indent=2)
