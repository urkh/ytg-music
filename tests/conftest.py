import os

import pytest


@pytest.fixture(autouse=True)
def force_anonymous_mode(mocker):
    """
    Forces all tests to run in anonymous mode by default
    """
    original_exists = os.path.exists

    def mocked_exists(path):
        if 'headers_auth.json' in str(path):
            return False
        return original_exists(path)

    mocker.patch('os.path.exists', side_effect=mocked_exists)


@pytest.fixture(autouse=True)
def mock_run_in_background(mocker):
    """
    Intervenes the worker's `run_in_background` function so that it runs
    synchronously during tests, avoiding thread concurrency issues.
    """

    def sync_run(task_func, callback, *args, **kwargs):
        try:
            result = task_func(*args, **kwargs)
            if callback:
                callback(result)
        except Exception:
            if callback:
                callback(None)

    mocker.patch('services.worker.run_in_background', side_effect=sync_run)


@pytest.fixture(scope='module')
def vcr_config():
    # Global VCR config
    return {
        'filter_headers': [
            ('Authorization', 'DUMMY_AUTHORIZATION'),
            ('Cookie', 'DUMMY_COOKIE'),
            ('x-origin', 'DUMMY_ORIGIN'),
        ],
        'decode_compressed_response': True,
        'record_mode': 'once',
    }
