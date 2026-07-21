import logging
import sys


def setup_logging(level: int = logging.INFO) -> None:
    formatter = logging.Formatter(fmt='[%(asctime)s] [%(levelname)s] [%(name)s]: %(message)s', datefmt='%H:%M:%S')

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)

    root_logger = logging.getLogger('ytgmusic')
    root_logger.setLevel(level)

    if not root_logger.handlers:
        root_logger.addHandler(console_handler)


def get_logger(name: str) -> logging.Logger:
    if not name.startswith('ytgmusic.'):
        name = f'ytgmusic.{name}'
    return logging.getLogger(name)
