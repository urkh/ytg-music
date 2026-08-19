from concurrent.futures import ThreadPoolExecutor
from typing import Any, Callable, Optional

from gi.repository import GLib

from utils.logger import get_logger

logger = get_logger(__name__)

# Bounded thread pool for general background tasks
_executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix='worker')


def run_in_background(
    task_func: Callable[[], Any],
    on_complete: Optional[Callable[[Any], Any]] = None,
    on_error: Optional[Callable[[Exception], Any]] = None,
) -> None:
    """
    Executes 'task_func' in a background thread using a bounded ThreadPoolExecutor.
    When it finishes, uses 'GLib.idle_add' to execute 'on_complete' or 'on_error' in the main UI thread.
    """

    def worker():
        try:
            result = task_func()
            if on_complete:
                GLib.idle_add(on_complete, result)
        except Exception as e:
            if on_error:
                GLib.idle_add(on_error, e)
            else:
                logger.error(f'Error in background task: {e}')
                if on_complete:
                    GLib.idle_add(on_complete, None)

    _executor.submit(worker)
