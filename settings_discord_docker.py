import os

SERVER = {
    "TYPE": "discord",
    "TOKEN": os.environ.get("HELGA_DISCORD_TOKEN", ""),
}

NICK = os.environ.get("HELGA_NICK", "helga")

CHANNELS = [
    ("#helga-dev",),
]

CHANNEL_LOGGING = os.environ.get("HELGA_CHANNEL_LOGGING", "0") == "1"

DATABASE = {
    "HOST": os.environ.get("HELGA_DATABASE_HOST", "postgres"),
    "PORT": int(os.environ.get("HELGA_DATABASE_PORT", "5432")),
    "DB": os.environ.get("HELGA_DATABASE_DB", "helga"),
    "USERNAME": os.environ.get("HELGA_DATABASE_USERNAME", "helga"),
    "PASSWORD": os.environ.get("HELGA_DATABASE_PASSWORD", "helga"),
}
