"""Constants for the Apple TV Control integration."""

import pyatv.exceptions

DOMAIN = "apple_tv_control"
NAME = "Apple TV Control"
VERSION = "2026.11.7"

# Platforms to set up
PLATFORMS = ["media_player", "button"]

# Config entry data keys
CONF_CREDENTIALS = "credentials"  # {pyatv Protocol name: credentials}
CONF_IDENTIFIER = "identifier"
CONF_HOST = "host"
CONF_NAME = "name"

# Default values
DEFAULT_NAME = "Apple TV"

# Update interval for polling fallback (seconds)
UPDATE_INTERVAL = 30

# Reconnection settings
MAX_RECONNECT_ATTEMPTS = 3
RECONNECT_DELAY = 5  # Base delay in seconds, with exponential backoff

# pyatv has no common base exception class, so collect every exception it defines
PYATV_ERRORS: tuple[type[Exception], ...] = tuple(
    obj
    for obj in vars(pyatv.exceptions).values()
    if isinstance(obj, type)
    and issubclass(obj, Exception)
    and obj.__module__ == pyatv.exceptions.__name__
)
