"""
IBM Cloud specific settings for Helga bot

This configuration file is designed to work with IBM Cloud Foundry and
uses environment variables for configuration that can be set via the
IBM Cloud dashboard or CLI.
"""

import json
import os

# Parse VCAP_SERVICES for MongoDB connection
vcap_services = os.environ.get("VCAP_SERVICES")
mongodb_credentials = {}

if vcap_services:
    try:
        services = json.loads(vcap_services)
    except (json.JSONDecodeError, ValueError):
        services = {}
    # Look for MongoDB service (could be 'compose-for-mongodb' or 'databases-for-mongodb')
    for service_type in ["compose-for-mongodb", "databases-for-mongodb", "mongodb"]:
        if service_type in services:
            try:
                mongodb_credentials = services[service_type][0]["credentials"]
            except (KeyError, IndexError, TypeError):
                pass
            break

# Bot nickname
NICK = os.environ.get("HELGA_NICK", "helga")

# IRC Server Configuration
# These should be set as environment variables in IBM Cloud
SERVER = {
    "HOST": os.environ.get("HELGA_IRC_HOST", "irc.freenode.net"),
    "PORT": int(os.environ.get("HELGA_IRC_PORT", "6667")),
    "SSL": os.environ.get("HELGA_IRC_SSL", "false").lower() == "true",
}

# Optional IRC authentication
if os.environ.get("HELGA_IRC_USERNAME"):
    SERVER["USERNAME"] = os.environ.get("HELGA_IRC_USERNAME")
if os.environ.get("HELGA_IRC_PASSWORD"):
    SERVER["PASSWORD"] = os.environ.get("HELGA_IRC_PASSWORD")

# Channels to join
# Format: comma-separated list, e.g., "#bots,#helga-dev"
channels_str = os.environ.get("HELGA_CHANNELS", "#bots")
CHANNELS = [(channel.strip(),) for channel in channels_str.split(",")]

# MongoDB Configuration
if mongodb_credentials:
    # IBM Cloud MongoDB service
    DATABASE = {
        "HOST": mongodb_credentials.get("host", "localhost"),
        "PORT": mongodb_credentials.get("port", 27017),
        "DB": mongodb_credentials.get("database", "helga"),
    }

    # Add authentication if provided
    if "username" in mongodb_credentials:
        DATABASE["USERNAME"] = mongodb_credentials["username"]
    if "password" in mongodb_credentials:
        DATABASE["PASSWORD"] = mongodb_credentials["password"]

    # Handle connection string if provided
    if "uri" in mongodb_credentials:
        # Parse MongoDB URI for connection details
        # This is a simplified parser; you may need to enhance it
        uri = mongodb_credentials["uri"]
        DATABASE["URI"] = uri
else:
    # Fallback to environment variables
    DATABASE = {
        "HOST": os.environ.get("HELGA_MONGO_HOST", "localhost"),
        "PORT": int(os.environ.get("HELGA_MONGO_PORT", "27017")),
        "DB": os.environ.get("HELGA_MONGO_DB", "helga"),
    }

    if os.environ.get("HELGA_MONGO_USERNAME"):
        DATABASE["USERNAME"] = os.environ.get("HELGA_MONGO_USERNAME")
    if os.environ.get("HELGA_MONGO_PASSWORD"):
        DATABASE["PASSWORD"] = os.environ.get("HELGA_MONGO_PASSWORD")

# Logging Configuration
LOG_LEVEL = os.environ.get("HELGA_LOG_LEVEL", "INFO")
LOG_FILE = None  # Log to stdout in cloud environment

# Auto-reconnect settings
AUTO_RECONNECT = True
AUTO_RECONNECT_DELAY = 5

# Operators (comma-separated list of nicks)
operators_str = os.environ.get("HELGA_OPERATORS", "")
OPERATORS = [op.strip() for op in operators_str.split(",") if op.strip()]

# Plugin Configuration
ENABLED_PLUGINS = True
DISABLED_PLUGINS = []
DEFAULT_CHANNEL_PLUGINS = True

# Webhook Configuration
ENABLED_WEBHOOKS = True
DISABLED_WEBHOOKS = None
WEBHOOKS_PORT = int(os.environ.get("PORT", "8080"))

# Webhook credentials (optional)
webhook_user = os.environ.get("HELGA_WEBHOOK_USER")
webhook_pass = os.environ.get("HELGA_WEBHOOK_PASS")
if webhook_user and webhook_pass:
    WEBHOOKS_CREDENTIALS = [(webhook_user, webhook_pass)]
else:
    WEBHOOKS_CREDENTIALS = []

# Command prefix settings
COMMAND_PREFIX_BOTNICK = True
COMMAND_PREFIX_CHAR = os.environ.get("HELGA_COMMAND_PREFIX", "!")

# Channel logging
CHANNEL_LOGGING = os.environ.get("HELGA_CHANNEL_LOGGING", "false").lower() == "true"
CHANNEL_LOGGING_DIR = os.environ.get("HELGA_CHANNEL_LOGGING_DIR", ".logs")

# Made with Bob
