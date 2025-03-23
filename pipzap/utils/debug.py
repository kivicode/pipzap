import os


def is_debug() -> bool:
    """Whether the `PIPZAP_DEBUG` env variable is set to '1'."""
    return os.environ.get("PIPZAP_DEBUG") == "1"
