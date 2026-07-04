from unittest.mock import Mock, call, patch

from pretend import stub

from helga.plugins import ACKS, operator


def test_operator_ignores_non_oper_user():
    client = stub(operators=["me"])
    formatted_nopes = (s.format(nick="sduncan") for s in operator.nopes)
    assert operator.operator(client, "#bots", "sduncan", "do something", "", "") in formatted_nopes


def test_operator_returns_usage_when_no_args():
    client = stub(operators=["me"])
    assert "Usage:" in operator.operator(client, "#bots", "me", "helga operator", "operator", [])


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
@patch("helga.plugins.operator.do_remove_autojoin")
@patch("helga.plugins.operator.do_add_autojoin")
def test_operator_handles_subcmd(do_add_autojoin, do_remove_autojoin, reload_plugin):
    do_add_autojoin.return_value = "add_autojoin"
    do_remove_autojoin.return_value = "remove_autojoin"
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
    assert operator.operator(*(args + [["reload"]])) == "Usage: helga operator reload <plugin>"


@patch("helga.plugins.operator.add_autojoin")
def test_do_add_autojoin_exists(add_autojoin):
    add_autojoin.return_value = False
    assert operator.do_add_autojoin("#foo") not in ACKS


@patch("helga.plugins.operator.add_autojoin")
def test_do_add_autojoin_adds(add_autojoin):
    add_autojoin.return_value = True
    assert operator.do_add_autojoin("foo") in ACKS
    add_autojoin.assert_called_with("foo")


@patch("helga.plugins.operator.remove_autojoin")
def test_do_remove_autojoin(remove_autojoin):
    assert operator.do_remove_autojoin("foo") in ACKS
    remove_autojoin.assert_called_with("foo")


@patch("helga.plugins.operator.get_connection")
@patch("helga.plugins.operator.get_autojoin_channels")
def test_join_autojoined_channels(get_autojoin_channels, get_connection):
    client = Mock()
    get_connection.return_value = Mock()
    get_autojoin_channels.return_value = ["#bots", "☃"]
    operator.join_autojoined_channels(client)
    assert client.join.call_args_list == [call("#bots"), call("☃")]


def test_list_operators_on_join():
    client = Mock(operators={"delta", "alpha"})
    operator.list_operators_on_join(client, "#bots")
    client.msg.assert_called_once_with("#bots", "Configured operators: alpha, delta")


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


@patch("helga.plugins.operator.reactor")
@patch("helga.plugins.operator.os")
@patch("helga.plugins.operator.shutil")
def test_operator_restart(mock_shutil, mock_os, mock_reactor):
    mock_shutil.which.return_value = "/usr/bin/helga"
    client = Mock(operators=["me"])
    result = operator.operator(client, "#bots", "me", "message", "operator", ["restart"])
    assert result == "Restarting..."
    mock_reactor.callLater.assert_called_once()
    assert mock_reactor.callLater.call_args[0][0] == 1
    assert mock_reactor.callLater.call_args[0][1] is mock_os.execv
    assert mock_reactor.callLater.call_args[0][2] == "/usr/bin/helga"
    assert mock_reactor.callLater.call_args[0][3] == ["/usr/bin/helga"] + operator.sys.argv[1:]


@patch("helga.plugins.operator.reactor")
def test_operator_quit(mock_reactor):
    client = Mock(operators=["me"])
    result = operator.operator(client, "#bots", "me", "message", "operator", ["quit"])
    assert result == "Shutting down..."
    mock_reactor.callLater.assert_called_once_with(1, mock_reactor.stop)
