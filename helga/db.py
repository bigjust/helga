"""
PostgreSQL connection objects and utilities
"""

import warnings

import psycopg2
from psycopg2.extras import RealDictCursor

from helga import settings


def connect():
    """
    Connect to a PostgreSQL instance, if helga is configured to do so (see setting
    :data:`~helga.settings.DATABASE`). This will return the PostgreSQL connection
    as configured.

    :returns: A `psycopg2.connection` instance, or ``None`` if the connection failed.
    """
    db_settings = getattr(settings, "DATABASE", {})

    params = {
        "host": db_settings.get("HOST", "localhost"),
        "port": db_settings.get("PORT", 5432),
        "dbname": db_settings.get("DB", "helga"),
        "user": db_settings.get("USERNAME", "helga"),
    }
    if "PASSWORD" in db_settings:
        params["password"] = db_settings["PASSWORD"]

    try:
        conn = psycopg2.connect(cursor_factory=RealDictCursor, **params)
    except psycopg2.OperationalError:
        warnings.warn("PostgreSQL is not available. Some features may not work", stacklevel=2)
        return None

    _ensure_tables(conn)
    return conn


def get_connection():
    """
    Return the shared PostgreSQL connection, creating it on first call.
    """
    global _connection
    if _connection is None:
        _connection = connect()
    return _connection


def _ensure_tables(conn):
    """Create the tables helga expects if they do not already exist."""
    with conn.cursor() as cur:
        cur.execute("""
            CREATE TABLE IF NOT EXISTS autojoin (
                channel TEXT PRIMARY KEY
            )
            """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS auto_enabled_plugins (
                plugin TEXT PRIMARY KEY,
                channels TEXT[] NOT NULL DEFAULT '{}'
            )
            """)
    conn.commit()


def get_autojoin_channels():
    """
    Return a list of all channels configured to be autojoined.
    """
    conn = get_connection()
    if conn is None:
        return []

    with conn.cursor() as cur:
        cur.execute("SELECT channel FROM autojoin ORDER BY channel")
        return [row["channel"] for row in cur.fetchall()]


def add_autojoin(channel):
    """
    Add a channel to the autojoin list.

    :returns: True if the channel was added, False if it was already present.
    """
    conn = get_connection()
    if conn is None:
        return False

    with conn.cursor() as cur:
        cur.execute(
            "INSERT INTO autojoin (channel) VALUES (%s) ON CONFLICT (channel) DO NOTHING",
            (channel,),
        )
        added = cur.rowcount == 1
    conn.commit()
    return added


def remove_autojoin(channel):
    """
    Remove a channel from the autojoin list.
    """
    conn = get_connection()
    if conn is None:
        return

    with conn.cursor() as cur:
        cur.execute("DELETE FROM autojoin WHERE channel = %s", (channel,))
    conn.commit()


def get_auto_enabled_plugins():
    """
    Return a list of dicts mapping plugin name to the channels on which it is
    auto-enabled.
    """
    conn = get_connection()
    if conn is None:
        return []

    with conn.cursor() as cur:
        cur.execute("SELECT plugin, channels FROM auto_enabled_plugins ORDER BY plugin")
        return [dict(row) for row in cur.fetchall()]


def get_auto_enabled_plugin(plugin):
    """
    Return the record for a single auto-enabled plugin, or None.
    """
    conn = get_connection()
    if conn is None:
        return None

    with conn.cursor() as cur:
        cur.execute(
            "SELECT plugin, channels FROM auto_enabled_plugins WHERE plugin = %s", (plugin,)
        )
        row = cur.fetchone()
        return dict(row) if row else None


def set_auto_enabled_channels(plugin, channels):
    """
    Set the channel list for an auto-enabled plugin, creating the record if
    necessary.
    """
    conn = get_connection()
    if conn is None:
        return

    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO auto_enabled_plugins (plugin, channels)
            VALUES (%s, %s)
            ON CONFLICT (plugin) DO UPDATE SET channels = EXCLUDED.channels
            """,
            (plugin, list(channels)),
        )
    conn.commit()


def add_auto_enabled_channel(plugin, channel):
    """
    Add a channel to the auto-enable list for a plugin.
    """
    rec = get_auto_enabled_plugin(plugin)
    channels = rec["channels"] if rec else []
    if channel not in channels:
        channels.append(channel)
        set_auto_enabled_channels(plugin, channels)


def remove_auto_enabled_channel(plugin, channel):
    """
    Remove a channel from the auto-enable list for a plugin.
    """
    rec = get_auto_enabled_plugin(plugin)
    if rec is None or channel not in rec["channels"]:
        return

    channels = rec["channels"]
    channels.remove(channel)
    set_auto_enabled_channels(plugin, channels)


_connection = None
