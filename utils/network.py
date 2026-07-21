import time
from typing import Any, Callable

import requests

from utils.logger import get_logger

logger = get_logger(__name__)


def with_retries(func: Callable[..., Any], max_retries: int = 2, delay: float = 0.5) -> Callable[..., Any]:
    """Wraps a function with automatic retry logic for network failures"""

    def wrapper(*args: Any, **kwargs: Any) -> Any:
        last_exception = None
        for attempt in range(max_retries + 1):
            try:
                return func(*args, **kwargs)
            except (
                requests.exceptions.RequestException,
                OSError,
                TimeoutError,
                ConnectionError,
            ) as e:
                last_exception = e
                if attempt < max_retries:
                    sleep_time = delay * (2**attempt)
                    logger.warning(
                        f'Network error in {func.__name__} (attempt {attempt + 1}/{max_retries + 1}): {e}. '
                        f'Retrying in {sleep_time}s...'
                    )
                    time.sleep(sleep_time)
                else:
                    logger.error(f'Fatal error in {func.__name__} after {max_retries + 1} attempts: {e}')
        if last_exception:
            raise last_exception

    return wrapper
