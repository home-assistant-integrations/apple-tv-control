"""Constants for the Apple TV Control integration."""

DOMAIN = "apple_tv_control"
NAME = "Apple TV Control"
VERSION = "0.1.0"

# Platforms to set up
PLATFORMS = ["media_player", "button"]

# Config entry data keys
CONF_MRP_CREDENTIALS = "mrp_credentials"
CONF_COMPANION_CREDENTIALS = "companion_credentials"
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

