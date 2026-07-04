from unittest.mock import Mock, call, patch

from helga.plugins import manager


@patch("helga.plugins.manager.get_connection")
@patch("helga.plugins.manager.get_auto_enabled_plugins")
@patch("helga.plugins.manager.registry")
def test_auto_enable_plugins(plugins, get_auto_enabled_plugins, get_connection):
    client = Mock()
    get_connection.return_value = Mock()
    rec = {"plugin": "haiku", "channels": ["a", "b", "c"]}
    get_auto_enabled_plugins.return_value = [rec]
    plugins.all_plugins = ["haiku"]

    manager.auto_enable_plugins(client)
    assert plugins.enable.call_args_list == [
        call("a", "haiku"),
        call("b", "haiku"),
        call("c", "haiku"),
    ]


@patch("helga.plugins.manager.registry")
def test_list_plugins(plugins):
    client = Mock()
    plugins.all_plugins = {"plugin1", "plugin2", "plugin3"}
    plugins.enabled_plugins = {"foo": {"plugin2"}}

    resp = manager.list_plugins(client, "foo")
    assert "Plugins enabled on this channel: plugin2" in resp
    assert "Available plugins: plugin1, plugin3" in resp


@patch("helga.plugins.manager.registry")
def test_list_plugins_handles_unicode(plugins):
    client = Mock()
    snowman = "☃"
    poo = "💩"

    plugins.all_plugins = {snowman, poo}
    plugins.enabled_plugins = {"foo": {poo}}

    resp = manager.list_plugins(client, "foo")
    assert f"Plugins enabled on this channel: {poo}" in resp
    assert f"Available plugins: {snowman}" in resp


@patch("helga.plugins.manager.add_auto_enabled_channel")
@patch("helga.plugins.manager.registry")
def test_enable_plugins(plugins, add_auto_enabled_channel):
    client = Mock()

    plugins.all_plugins = ["foobar"]

    manager.enable_plugins(client, "#bots", "foobar")

    add_auto_enabled_channel.assert_called_with("foobar", "#bots")


@patch("helga.plugins.manager._filter_valid")
def test_enable_plugins_no_plugins(filter_valid):
    snowman = "☃"
    filter_valid.return_value = []
    plugins = ["foo", "bar", snowman]  # Test unicode

    resp = manager.enable_plugins(None, None, *plugins)
    expect = "Sorry, but I don't know about these plugins: {}, {}, {}".format("foo", "bar", snowman)
    assert resp == expect


@patch("helga.plugins.manager.remove_auto_enabled_channel")
@patch("helga.plugins.manager._filter_valid")
@patch("helga.plugins.manager.registry")
def test_disable_plugins(plugins, filter_valid, remove_auto_enabled_channel):
    client = Mock()
    plugins.all_plugins = ["foobar", "blah", "no_record"]
    filter_valid.return_value = plugins.all_plugins

    manager.disable_plugins(client, "#bots", *plugins.all_plugins)
    remove_auto_enabled_channel.assert_has_calls(
        [
            call("foobar", "#bots"),
            call("blah", "#bots"),
            call("no_record", "#bots"),
        ]
    )


@patch("helga.plugins.manager._filter_valid")
def test_disable_plugins_no_plugins(filter_valid):
    snowman = "☃"
    filter_valid.return_value = []
    plugins = ["foo", "bar", snowman]  # Test unicode

    resp = manager.disable_plugins(None, None, *plugins)
    expect = "Sorry, but I don't know about these plugins: {}, {}, {}".format("foo", "bar", snowman)
    assert resp == expect


@patch("helga.plugins.manager.disable_plugins")
@patch("helga.plugins.manager.enable_plugins")
@patch("helga.plugins.manager.list_plugins")
def test_manager_plugin(list, enable, disable):
    list.return_value = "list"
    enable.return_value = "enable"
    disable.return_value = "disable"

    assert manager.manager("client", "#bots", "me", "message", "plugins", []) == "list"
    assert manager.manager("client", "#bots", "me", "message", "plugins", ["list"]) == "list"
    assert manager.manager("client", "#bots", "me", "message", "plugins", ["enable"]) == "enable"
    assert manager.manager("client", "#bots", "me", "message", "plugins", ["disable"]) == "disable"
    assert manager.manager("client", "#bots", "me", "message", "plugins", ["lol"]) is None
