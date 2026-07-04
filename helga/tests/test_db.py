from unittest.mock import MagicMock, Mock, patch

import psycopg2

from helga import db


def _make_conn():
    """Return a mock psycopg2 connection that supports the cursor context manager."""
    conn = MagicMock()
    cur = MagicMock()
    conn.cursor.return_value.__enter__ = Mock(return_value=cur)
    conn.cursor.return_value.__exit__ = Mock(return_value=False)
    return conn, cur


@patch("helga.db.psycopg2.connect")
@patch("helga.db.settings")
def test_connect_returns_none_on_failure(settings, connect):
    settings.DATABASE = {
        "HOST": "localhost",
        "PORT": "1234",
        "DB": "baz",
        "USERNAME": "user",
    }

    connect.side_effect = psycopg2.OperationalError
    assert db.connect() is None


@patch("helga.db.psycopg2.connect")
@patch("helga.db.settings")
def test_connect_returns_connection(settings, connect):
    settings.DATABASE = {
        "HOST": "localhost",
        "PORT": "1234",
        "DB": "baz",
        "USERNAME": "user",
        "PASSWORD": "pass",
    }

    conn, _ = _make_conn()
    connect.return_value = conn

    assert db.connect() is conn
    connect.assert_called_once()
    call_kwargs = connect.call_args.kwargs
    assert call_kwargs["host"] == "localhost"
    assert call_kwargs["port"] == "1234"
    assert call_kwargs["dbname"] == "baz"
    assert call_kwargs["user"] == "user"
    assert call_kwargs["password"] == "pass"


@patch("helga.db.get_connection")
def test_get_autojoin_channels(get_connection):
    conn, cur = _make_conn()
    get_connection.return_value = conn
    cur.fetchall.return_value = [{"channel": "#foo"}, {"channel": "#bar"}]

    assert db.get_autojoin_channels() == ["#foo", "#bar"]


@patch("helga.db.get_connection")
def test_get_autojoin_channels_no_connection(get_connection):
    get_connection.return_value = None
    assert db.get_autojoin_channels() == []


@patch("helga.db.get_connection")
def test_add_autojoin_new(get_connection):
    conn, cur = _make_conn()
    get_connection.return_value = conn
    cur.rowcount = 1

    assert db.add_autojoin("#foo") is True
    conn.commit.assert_called()


@patch("helga.db.get_connection")
def test_add_autojoin_existing(get_connection):
    conn, cur = _make_conn()
    get_connection.return_value = conn
    cur.rowcount = 0

    assert db.add_autojoin("#foo") is False


@patch("helga.db.get_connection")
def test_remove_autojoin(get_connection):
    conn, _ = _make_conn()
    get_connection.return_value = conn
    db.remove_autojoin("#foo")
    conn.commit.assert_called()


@patch("helga.db.get_connection")
def test_get_auto_enabled_plugins(get_connection):
    conn, cur = _make_conn()
    get_connection.return_value = conn
    cur.fetchall.return_value = [
        {"plugin": "foo", "channels": ["#a", "#b"]},
    ]

    assert db.get_auto_enabled_plugins() == [{"plugin": "foo", "channels": ["#a", "#b"]}]


@patch("helga.db.get_connection")
def test_get_auto_enabled_plugin(get_connection):
    conn, cur = _make_conn()
    get_connection.return_value = conn
    cur.fetchone.return_value = {"plugin": "foo", "channels": ["#a"]}

    assert db.get_auto_enabled_plugin("foo") == {"plugin": "foo", "channels": ["#a"]}


@patch("helga.db.get_connection")
def test_get_auto_enabled_plugin_missing(get_connection):
    conn, cur = _make_conn()
    get_connection.return_value = conn
    cur.fetchone.return_value = None

    assert db.get_auto_enabled_plugin("foo") is None


@patch("helga.db.get_connection")
def test_set_auto_enabled_channels(get_connection):
    conn, _ = _make_conn()
    get_connection.return_value = conn
    db.set_auto_enabled_channels("foo", ["#a", "#b"])
    conn.commit.assert_called()


@patch("helga.db.get_auto_enabled_plugin")
@patch("helga.db.set_auto_enabled_channels")
def test_add_auto_enabled_channel_new(set_channels, get_plugin):
    get_plugin.return_value = None
    db.add_auto_enabled_channel("foo", "#bots")
    set_channels.assert_called_with("foo", ["#bots"])


@patch("helga.db.get_auto_enabled_plugin")
@patch("helga.db.set_auto_enabled_channels")
def test_add_auto_enabled_channel_existing(set_channels, get_plugin):
    get_plugin.return_value = {"plugin": "foo", "channels": ["#bots"]}
    db.add_auto_enabled_channel("foo", "#bots")
    set_channels.assert_not_called()


@patch("helga.db.get_auto_enabled_plugin")
@patch("helga.db.set_auto_enabled_channels")
def test_remove_auto_enabled_channel(set_channels, get_plugin):
    get_plugin.return_value = {"plugin": "foo", "channels": ["#bots", "#other"]}
    db.remove_auto_enabled_channel("foo", "#bots")
    set_channels.assert_called_with("foo", ["#other"])
