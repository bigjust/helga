import os

NICK = os.environ.get("HELGA_NICK", "helga")

SERVER = {
    "HOST": os.environ.get("HELGA_IRC_SERVER", "localhost"),
    "PORT": 6667,
    "SSL": False,
}

CHANNELS = [
    ("#helga-dev",),
]

DATABASE = {
    "HOST": os.environ.get("HELGA_DATABASE_HOST", "postgres"),
    "PORT": int(os.environ.get("HELGA_DATABASE_PORT", "5432")),
    "DB": os.environ.get("HELGA_DATABASE_DB", "helga"),
    "USERNAME": os.environ.get("HELGA_DATABASE_USERNAME", "helga"),
    "PASSWORD": os.environ.get("HELGA_DATABASE_PASSWORD", "helga"),
}

# Made with Bob
