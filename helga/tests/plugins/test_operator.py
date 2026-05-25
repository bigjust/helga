from unittest.mock import Mock, call, patch

from pretend import stub

from helga.plugins import ACKS, operator


def test_operator_ignores_non_oper_user():
    client = stub(operators=["me"])
    formatted_nopes = (s.format(nick="sduncan") for s in operator.nopes)
    assert operator.operator(client, "#bots", "sduncan", "do something", "", "") in formatted_nopes


def test_operator_join_calls_client_join():
    client = Mock(operators=["me"])
    operator.operator(client, "#bots", "me", "do something", "op", ["join", "#foo"])
    client.join.assert_called_with("#foo")


def test_operator_join_ignores_invalid_channel():
    client = Mock(operators=["me"])
    operator.operator(client, "#bots", "me", "do something", "op", ["join", "foo"])
    assert not client.join.called


def test_operator_leave_calls_client_leave():
    client = Mock(operators=["me"])
    operator.operator(client, "#bots", "me", "do something", "op", ["leave", "#foo"])
    client.leave.assert_called_with("#foo")


def test_operator_leave_ignores_invalid_channel():
    client = Mock(operators=["me"])
    operator.operator(client, "#bots", "me", "do something", "op", ["leave", "foo"])
    assert not client.leave.called


@patch("helga.plugins.operator.reload_plugin")
@patch("helga.plugins.operator.remove_autojoin")
@patch("helga.plugins.operator.add_autojoin")
def test_operator_handles_subcmd(add_autojoin, remove_autojoin, reload_plugin):
    add_autojoin.return_value = "add_autojoin"
    remove_autojoin.return_value = "remove_autojoin"
    reload_plugin.return_value = "reload_plugin"

    client = Mock(operators=["me"])
    args = [client, "#bots", "me", "message", "operator"]

    # Client commands
    for cmd in ("join", "leave"):
        client.reset_mock()
        operator.operator(*(args + [[cmd, "#foo"]]))
        getattr(client, cmd).assert_called_with("#foo")

    # Autojoin add/remove
    assert operator.operator(*(args + [["autojoin", "add", "#foo"]])) == "add_autojoin"
    assert operator.operator(*(args + [["autojoin", "remove", "#foo"]])) == "remove_autojoin"

    # The feature that shall not be named
    operator.operator(*(args + [["nsa", "#other_chan", "unicode", "snowman", "☃"]]))
    client.msg.assert_called_with("#other_chan", "unicode snowman ☃")

    assert operator.operator(*(args + [["reload", "foo"]])) == "reload_plugin"


@patch("helga.plugins.operator.db")
def test_add_autojoin_exists(db):
    db.autojoin.find.return_value = db
    db.count.return_value = 1
    assert operator.add_autojoin("#foo") not in ACKS


@patch("helga.plugins.operator.db")
def test_add_autojoin_adds(db):
    db.autojoin.find.return_value = db
    db.count.return_value = 0
    operator.add_autojoin("foo")
    db.autojoin.insert.assert_called_with({"channel": "foo"})


@patch("helga.plugins.operator.db")
def test_remove_autojoin(db):
    operator.remove_autojoin("foo")
    db.autojoin.remove.assert_called_with({"channel": "foo"})


@patch("helga.plugins.operator.db")
def test_join_autojoined_channels(db):
    client = Mock()
    db.autojoin.find.return_value = [
        {"channel": "#bots"},
        {"channel": "☃"},
    ]
    operator.join_autojoined_channels(client)
    assert client.join.call_args_list == [call("#bots"), call("☃")]


@patch("helga.plugins.operator.registry")
def test_reload_plugin(plugins):
    plugins.reload.return_value = True
    assert operator.reload_plugin("foo") == "Successfully reloaded plugin 'foo'"

    plugins.reload.return_value = False
    assert operator.reload_plugin("foo") == "Failed to reload plugin 'foo'"


@patch("helga.plugins.operator.registry")
def test_reload_plugin_handles_unicode(plugins):
    snowman = "☃"
    plugins.reload.return_value = True
    assert f"Successfully reloaded plugin '{snowman}'" == operator.reload_plugin(snowman)

    plugins.reload.return_value = False
    assert f"Failed to reload plugin '{snowman}'" == operator.reload_plugin(snowman)
