import gc


def free_memory():
    """
    Forces Python garbage collection.
    Returns False so it can be safely used with GLib.idle_add or GLib.timeout_add
    without executing cyclically.
    """
    gc.collect()
    return False
