import hashlib
import math
import os
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Optional

import cairo
import gi
import requests

gi.require_version('Gtk', '4.0')
gi.require_version('Gdk', '4.0')
gi.require_version('GdkPixbuf', '2.0')
from gi.repository import Gdk, GdkPixbuf, Gio, GLib, Gtk  # noqa: E402

from utils.logger import get_logger  # noqa: E402

logger = get_logger(__name__)

# Bounded thread pool for downloading and processing thumbnail images
_image_executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix='image-loader')


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

    max_radius = min(width, height) / 2
    actual_radius = min(float(radius), max_radius)

    surface = cairo.ImageSurface(cairo.Format.ARGB32, width, height)
    cr = cairo.Context(surface)

    cr.arc(actual_radius, actual_radius, actual_radius, math.pi, 1.5 * math.pi)
    cr.arc(width - actual_radius, actual_radius, actual_radius, 1.5 * math.pi, 2 * math.pi)
    cr.arc(width - actual_radius, height - actual_radius, actual_radius, 0, 0.5 * math.pi)
    cr.arc(actual_radius, height - actual_radius, actual_radius, 0.5 * math.pi, math.pi)
    cr.close_path()

    cr.clip()

    Gdk.cairo_set_source_pixbuf(cr, pixbuf, 0, 0)
    cr.paint()

    res_pixbuf = Gdk.pixbuf_get_from_surface(surface, 0, 0, width, height)
    surface.finish()
    return res_pixbuf


def process_pixbuf(
    pixbuf: GdkPixbuf.Pixbuf,
    is_circular: bool = False,
    is_unrounded: bool = False,
    max_size: int = 200,
    max_width: Optional[int] = None,
    max_height: Optional[int] = None,
) -> GdkPixbuf.Pixbuf:
    """Processes a Pixbuf by downscaling with aspect ratio preservation and optional rounding"""
    if not is_unrounded and is_circular:
        w = pixbuf.get_width()
        h = pixbuf.get_height()
        if w != h:
            min_dim = min(w, h)
            offset_x = (w - min_dim) // 2
            offset_y = (h - min_dim) // 2
            pixbuf = pixbuf.new_subpixbuf(offset_x, offset_y, min_dim, min_dim)

    orig_w = pixbuf.get_width()
    orig_h = pixbuf.get_height()

    target_max_w = max_width if max_width is not None else max_size
    target_max_h = max_height if max_height is not None else max_size

    if target_max_w and target_max_h and (orig_w > target_max_w or orig_h > target_max_h):
        scale = min(target_max_w / orig_w, target_max_h / orig_h)
        new_w = max(1, int(round(orig_w * scale)))
        new_h = max(1, int(round(orig_h * scale)))
        pixbuf = pixbuf.scale_simple(new_w, new_h, GdkPixbuf.InterpType.BILINEAR)

    if not is_unrounded:
        if is_circular:
            radius = pixbuf.get_width() / 2
            pixbuf = round_pixbuf(pixbuf, radius=int(radius))
        else:
            pixbuf = round_pixbuf(pixbuf, radius=16)

    return pixbuf


def load_image_async(
    url: Optional[str],
    image_widget: Any,
    is_circular: bool = False,
    is_unrounded: bool = False,
    max_size: int = 200,
    max_width: Optional[int] = None,
    max_height: Optional[int] = None,
) -> None:
    """Downloads an image and processes it with aspect-ratio-preserving downscaling"""
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
                        logger.warning(f'Error writing disk cache {disk_path}: {e}')

            if content:
                bytes_data = GLib.Bytes.new(content)
                stream = Gio.MemoryInputStream.new_from_bytes(bytes_data)
                pixbuf = GdkPixbuf.Pixbuf.new_from_stream(stream, None)
                stream.close()

                pixbuf = process_pixbuf(
                    pixbuf,
                    is_circular=is_circular,
                    is_unrounded=is_unrounded,
                    max_size=max_size,
                    max_width=max_width,
                    max_height=max_height,
                )

                def update_ui():
                    try:
                        texture = Gdk.Texture.new_for_pixbuf(pixbuf)
                        if isinstance(image_widget, Gtk.Picture):
                            image_widget.set_paintable(texture)
                        elif hasattr(image_widget, 'set_from_paintable'):
                            image_widget.set_from_paintable(texture)
                        elif hasattr(image_widget, 'set_paintable'):
                            image_widget.set_paintable(texture)
                    except Exception as e:
                        logger.warning(f'Error updating image UI: {e}')

                GLib.idle_add(update_ui)
        except Exception as e:
            logger.warning(f'Error downloading image {url}: {e}')

    _image_executor.submit(worker)
