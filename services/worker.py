import threading
from typing import Any, Callable, Optional

from gi.repository import GLib

from utils.logger import get_logger

logger = get_logger(__name__)


def run_in_background(
    task_func: Callable[[], Any],
    on_complete: Optional[Callable[[Any], Any]] = None,
    on_error: Optional[Callable[[Exception], Any]] = None,
) -> None:
    """
    Ejecuta 'task_func' en un hilo en segundo plano (Thread).
    Cuando termina, usa 'GLib.idle_add' para ejecutar 'on_complete' o 'on_error' en el hilo principal de la UI.
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
                logger.error(f'Error en tarea de segundo plano: {e}')
                if on_complete:
                    GLib.idle_add(on_complete, None)

    thread = threading.Thread(target=worker, daemon=True)
    thread.start()
