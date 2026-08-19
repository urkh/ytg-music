import json
import os
import tempfile
import uuid

import browsercookie
from gi.repository import GLib
from ytmusicapi import YTMusic
from ytmusicapi.ytmusic import get_authorization, sapisid_from_cookie

from utils.logger import get_logger

logger = get_logger(__name__)


def get_auth_file_path() -> str:
    """Returns the XDG Base Directory for saving session"""
    data_dir = os.path.join(GLib.get_user_data_dir(), 'ytg-music')
    os.makedirs(data_dir, exist_ok=True)
    target_path = os.path.join(data_dir, 'headers_auth.json')
    return target_path


def extract_browser_cookies() -> str:
    """Extracts and filters essential YouTube cookies from the local browser"""
    try:
        cj = browsercookie.firefox()
    except Exception:
        cj = browsercookie.chrome()

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

    filtered = [f'{c.name}={c.value}' for c in cj if 'youtube.com' in c.domain and c.name in essential_keys]

    if not filtered:
        raise Exception(
            'Error: The browser cookies are not present or are expired. Please, log in to YouTube Music and try again.'
        )

    return '; '.join(filtered)


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
                        'handle': info.get('channelHandle', f'Perfil {i}'),
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
