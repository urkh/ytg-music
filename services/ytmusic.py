import json
import os
from typing import Any, Optional

from ytmusicapi import YTMusic

from utils.auth import build_base_headers, extract_browser_cookies, get_auth_file_path
from utils.logger import get_logger
from utils.network import with_retries

logger = get_logger(__name__)


class APIProxy:
    """Singleton proxy to dynamically access and reload the ytmusicapi instance."""

    _instance: Optional[YTMusic] = None

    @classmethod
    def reload(cls) -> None:
        headers_path = get_auth_file_path()
        if os.path.exists(headers_path):
            try:
                # Silent cookie refresh (Google expires TS cookies very quickly now)
                try:
                    fresh_cookie_str = extract_browser_cookies()
                    fresh_base = build_base_headers(fresh_cookie_str)
                    with open(headers_path, 'r') as f:
                        headers_data = json.load(f)

                    headers_data['Cookie'] = fresh_base['Cookie']
                    if 'Authorization' in fresh_base:
                        headers_data['Authorization'] = fresh_base['Authorization']

                    with open(headers_path, 'w') as f:
                        json.dump(headers_data, f, indent=2)
                except Exception as e:
                    logger.debug(f'Refresco silencioso de cookies falló: {e}')

                cls._instance = YTMusic(headers_path)
                logger.info('YTMusic initialized with Cookies')
            except Exception as e:
                logger.error(f'Failed to load Cookies: {e}')
                cls._instance = YTMusic()
        else:
            cls._instance = YTMusic()
            logger.info('YTMusic initialized anonymously')

    def __getattr__(self, name: str) -> Any:
        if self.__class__._instance is None:
            self.__class__.reload()
        attr = getattr(self.__class__._instance, name)
        if callable(attr):
            return with_retries(attr)
        return attr


api = APIProxy()
reload_api = APIProxy.reload
reload_api()
