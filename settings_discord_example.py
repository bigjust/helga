"""
Example Discord configuration for Helga bot

To use this configuration:
1. Create a bot at https://discord.com/developers/applications
2. Copy its token and enable the privileged "Message Content" and
   "Server Members" intents in the bot settings (the backend requests them)
3. Invite the bot to your server with the ``bot`` scope
4. Run:
       helga --settings=settings_discord_example.py
"""

# Discord server configuration
SERVER = {
    "TYPE": "discord",
    # The bot token from the developer portal. ``BOT_TOKEN``, ``TOKEN`` and
    # ``API_KEY`` are all accepted.
    "TOKEN": "YOUR_BOT_TOKEN_HERE",
}

# Bot nickname is configured in the Discord developer portal and detected
# automatically from the READY event, so no need to set NICK here.

# Channels the bot "joins" are informational for Discord: it can see any
# channel it has permissions for and cannot join channels programmatically.
CHANNELS = [
    ("#general",),
    ("#bots",),
]

# Optional: log all channel traffic to helga/CHANNEL_LOGGING_DIR
CHANNEL_LOGGING = False
CHANNEL_LOGGING_DIR = ".logs"

# Bot operators (Discord usernames)
OPERATORS = [
    "your_username",
]

# Command prefix
COMMAND_PREFIX_CHAR = "!"

# Auto-reconnect settings
AUTO_RECONNECT = True
AUTO_RECONNECT_DELAY = 5

# Logging
LOG_LEVEL = "INFO"
