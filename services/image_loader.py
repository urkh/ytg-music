import hashlib
import math
import os
import threading

import cairo
import gi
import requests

gi.require_version('Gtk', '4.0')
gi.require_version('Gdk', '4.0')
gi.require_version('GdkPixbuf', '2.0')
from typing import Any, Optional
from gi.repository import Gdk, GdkPixbuf, Gio, GLib, Gtk  # noqa: E402

from utils.logger import get_logger  # noqa: E402

logger = get_logger(__name__)


def get_cache_dir() -> str:
    cache_dir = os.path.join(GLib.get_user_cache_dir(), 'ytg-music', 'thumbnails')
    os.makedirs(cache_dir, exist_ok=True)
    return cache_dir


def get_disk_cache_path(url: str) -> str:
    url_hash = hashlib.md5(url.encode('utf-8')).hexdigest()
    return os.path.join(get_cache_dir(), f'{url_hash}.img')


def round_pixbuf(pixbuf: GdkPixbuf.Pixbuf, radius: int = 12) -> GdkPixbuf.Pixbuf:
    width = pixbuf.get_width()
    height = pixbuf.get_height()

    surface = cairo.ImageSurface(cairo.Format.ARGB32, width, height)
    cr = cairo.Context(surface)

    cr.arc(radius, radius, radius, math.pi, 1.5 * math.pi)
    cr.arc(width - radius, radius, radius, 1.5 * math.pi, 2 * math.pi)
    cr.arc(width - radius, height - radius, radius, 0, 0.5 * math.pi)
    cr.arc(radius, height - radius, radius, 0.5 * math.pi, math.pi)
    cr.close_path()

    cr.clip()

    Gdk.cairo_set_source_pixbuf(cr, pixbuf, 0, 0)
    cr.paint()

    res_pixbuf = Gdk.pixbuf_get_from_surface(surface, 0, 0, width, height)
    surface.finish()
    return res_pixbuf


def load_image_async(
    url: Optional[str],
    image_widget: Any,
    is_circular: bool = False,
    is_unrounded: bool = False,
    max_size: int = 200,
) -> None:
    """Downloads an image asynchronously (disk-only cache, web style) and processes it with downscaling."""
    if not url:
        return

    def worker():
        try:
            disk_path = get_disk_cache_path(url)
            content = None
            if os.path.exists(disk_path):
                try:
                    with open(disk_path, 'rb') as f:
                        content = f.read()
                except Exception:
                    content = None

            if not content:
                response = requests.get(url, timeout=5)
                if response.status_code == 200:
                    content = response.content
                    try:
                        with open(disk_path, 'wb') as f:
                            f.write(content)
                    except Exception as e:
                        logger.warning(f'Error escribiendo caché en disco {disk_path}: {e}')

            if content:
                bytes_data = GLib.Bytes.new(content)
                stream = Gio.MemoryInputStream.new_from_bytes(bytes_data)
                pixbuf = GdkPixbuf.Pixbuf.new_from_stream(stream, None)
                stream.close()

                # Efficient downscaling in RAM
                if pixbuf.get_width() > max_size or pixbuf.get_height() > max_size:
                    pixbuf = pixbuf.scale_simple(max_size, max_size, GdkPixbuf.InterpType.BILINEAR)

                if not is_unrounded:
                    if is_circular:
                        radius = min(pixbuf.get_width(), pixbuf.get_height()) / 2
                        pixbuf = round_pixbuf(pixbuf, radius=radius)
                    else:
                        pixbuf = round_pixbuf(pixbuf, radius=16)  # 16px radius

                def update_ui():
                    texture = Gdk.Texture.new_for_pixbuf(pixbuf)
                    if isinstance(image_widget, Gtk.Picture):
                        image_widget.set_paintable(texture)
                    else:
                        image_widget.set_from_paintable(texture)

                GLib.idle_add(update_ui)
        except Exception as e:
            logger.warning(f'Error descargando imagen {url}: {e}')

    threading.Thread(target=worker, daemon=True).start()
