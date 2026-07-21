import gettext
import locale
import os
from typing import Callable

DOMAIN = 'ytgmusic'
LOCALEDIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'locales')

try:
    translation = gettext.translation(DOMAIN, LOCALEDIR, fallback=True)
    _: Callable[[str], str] = translation.gettext
except Exception:
    _ = gettext.gettext


def setup_i18n() -> None:
    try:
        locale.setlocale(locale.LC_ALL, '')
    except Exception:
        pass

    gettext.bindtextdomain(DOMAIN, LOCALEDIR)
    gettext.textdomain(DOMAIN)
