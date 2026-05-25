from unittest.mock import patch

import pytest

from helga.comm import slack


@pytest.fixture(scope="module", autouse=True)
def patch_api():
    with patch.object(slack, "api", return_value=None):
        yield


@pytest.fixture
def client():
    c = None

    with patch.object(slack, "task"):
        c = slack.Client(
            {
                "self": {
                    "name": "helga",
                },
            }
        )

    yield c


class TestClient:
    def test_parse_message_simple(self, client):
        message = "<@U1234ABC> Hi"

        with patch.object(client, "_get_user_name", return_value="adeza") as mock_get_user:
            result = client._parse_incoming_message(message)
            assert result == "@adeza Hi"
            mock_get_user.assert_called_with("U1234ABC")

    def test_parse_message_complex(self, client):
        message = "<@U1234ABC|alfredo> Hi"

        with patch.object(client, "_get_user_name", return_value="alfredo") as mock_get_user:
            result = client._parse_incoming_message(message)
            assert result == "@alfredo Hi"
            mock_get_user.assert_called_with("U1234ABC")

    def test_parse_message_unescape(self, client):
        message = "<@U1234ABC> test &lt;reply&gt; &amp; more"

        with patch.object(client, "_get_user_name", return_value="alfredo") as mock_get_user:
            result = client._parse_incoming_message(message)
            assert result == "@alfredo test <reply> & more"
            mock_get_user.assert_called_with("U1234ABC")

    def test_parse_incoming_message_channel(self, client):
        message = "<#C1234|general> hello"

        with patch.object(client, "_get_channel_name", return_value="general") as mock_get_chan:
            result = client._parse_incoming_message(message)
            assert result == "#general hello"
            mock_get_chan.assert_called_with("C1234")

    def test_get_channel_name(self, client):
        client._channel_names = {"C1234": "general"}
        assert client._get_channel_name("C1234") == "general"
        assert client._get_channel_name("UNKNOWN") == ""

    def test_get_channel_id(self, client):
        client._channel_names = {"C1234": "general", "C5678": "random"}
        assert client._get_channel_id("general") == "C1234"
        assert client._get_channel_id("#general") == "C1234"
        assert client._get_channel_id("nonexistent") is None

    def test_get_user_name(self, client):
        client._user_names = {"U1234": "adeza"}
        assert client._get_user_name("U1234") == "adeza"
        assert client._get_user_name("UNKNOWN") == ""

    def test_get_user_id(self, client):
        client._user_names = {"U1234": "adeza", "U5678": "helga"}
        assert client._get_user_id("adeza") == "U1234"
        assert client._get_user_id("@adeza") == "U1234"
        assert client._get_user_id("nonexistent") is None

    def test_sanitize(self, client):
        message = "look over there & <test>"
        result = client._sanitize(message)
        assert result == "look over there &amp; &lt;test&gt;"

    def test_slack_error(self):
        err = slack.SlackError(api="test.api", error="something_wrong")
        assert err.api == "test.api"
        assert err.error == "something_wrong"
        assert err.message == "something_wrong in test.api"
        assert str(err) == "something_wrong in test.api"

    def test_me(self, client):
        with patch.object(client, "_send_message") as send:
            client.me("#general", "waves")
            send.assert_called_with("#general", "waves", subtype="me_message")

    def test_send_message(self, client):
        client._channel_names = {"C123": "general"}
        with patch.object(client, "sendMessage") as send:
            client._send_message("C123", "hello")
            assert send.called
            import json

            data = json.loads(send.call_args[0][0])
            assert data["channel"] == "C123"
            assert data["text"] == "hello"
            assert data["type"] == "message"

    def test_send_message_resolves_channel_name(self, client):
        client._channel_names = {"C123": "general"}
        client._requests = {}
        with patch.object(client, "sendMessage") as send:
            client._send_message("general", "hello")
            import json

            data = json.loads(send.call_args[0][0])
            assert data["channel"] == "C123"

    def test_onMessageAck(self, client):
        client._requests = {42: {"text": "hello"}}
        client.onMessageAck(42, {"ok": True})
        assert 42 not in client._requests

    def test_onMessageAck_unknown(self, client):
        client._requests = {}
        response = {"ok": True}
        client.onMessageAck(99, response)

    def test_onMessageAck_error(self, client):
        client._requests = {1: {"text": "hi"}}
        response = {"ok": False, "error": "some_error"}
        client.onMessageAck(1, response)

    def test_slack_hello(self, client):
        with patch.object(slack, "smokesignal") as signal:
            client.slack_hello({"type": "hello"})
            signal.emit.assert_called_with("signon", client)

    def test_onMessage_ignores_reply_to(self, client):
        msg = '{"reply_to": 1, "ok": true}'
        with patch.object(client, "onMessageAck") as ack:
            client.onMessage(msg, False)
            ack.assert_called_with(1, {"reply_to": 1, "ok": True})

    def test_onMessage_ignores_noise(self, client):
        msg = '{"type": "desktop_notification"}'
        client.onMessage(msg, False)

        msg = '{"type": "user_typing"}'
        client.onMessage(msg, False)

    def test_onMessage_unhandled_type(self, client):
        msg = '{"type": "unknown_event"}'
        client.onMessage(msg, False)

    def test_onMessage_handles_bad_json(self, client):
        client.onMessage("not valid json", False)

    def test_onMessage_handles_no_type(self, client):
        msg = '{"key": "value"}'
        client.onMessage(msg, False)
