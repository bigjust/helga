import json
from unittest.mock import Mock, patch

import pytest

from helga.comm import discord


@pytest.fixture(autouse=True)
def run_deferred_sync():
    """
    Run deferToThread calls synchronously so tests don't touch the real
    thread pool (which would hit the network).
    """
    from twisted.internet.defer import fail, succeed

    def executor(fn, *a, **kw):
        try:
            return succeed(fn(*a, **kw))
        except Exception as e:  # pragma: no cover - error path exercised via errbacks
            return fail(e)

    with patch.object(discord.threads, "deferToThread", side_effect=executor):
        yield


@pytest.fixture
def client():
    bot_user = {
        "id": "123456789",
        "username": "helga",
    }
    with patch.object(discord, "task"):
        c = discord.Client(bot_user)
    yield c


class TestDiscordError:
    def test_properties(self):
        err = discord.DiscordError(
            api="channels/123/messages", status_code=403, error="Missing Access"
        )
        assert err.api == "channels/123/messages"
        assert err.status_code == 403
        assert err.error == "Missing Access"
        assert "HTTP 403: Missing Access in channels/123/messages" in str(err)

    def test_without_status_code(self):
        err = discord.DiscordError(api="gateway/bot", error="Connection timeout")
        assert err.status_code is None
        assert str(err) == "Connection timeout in gateway/bot"

    def test_without_error(self):
        err = discord.DiscordError(api="gateway/bot")
        assert str(err) == "Error in gateway/bot"


class TestApi:
    def test_api_get_success(self):
        mock_resp = Mock(status_code=200, content=b'{"url": "wss://gateway.discord.gg"}')
        mock_resp.json.return_value = {"url": "wss://gateway.discord.gg"}

        with patch("requests.request", return_value=mock_resp) as mock_req:
            with patch.dict(discord.settings.SERVER, {"BOT_TOKEN": "secret_token"}, clear=True):
                data = discord.api("gateway/bot")
                assert data == {"url": "wss://gateway.discord.gg"}
                mock_req.assert_called_once_with(
                    method="GET",
                    url="https://discord.com/api/v10/gateway/bot",
                    headers={
                        "Authorization": "Bot secret_token",
                        "Content-Type": "application/json",
                        "User-Agent": "Helga (https://github.com/bigjust/helga, 2.0.0)",
                    },
                    json=None,
                    params=None,
                )

    def test_api_full_url_and_post(self):
        mock_resp = Mock(status_code=200, content=b'{"id": "msg1"}')
        mock_resp.json.return_value = {"id": "msg1"}

        with patch("requests.request", return_value=mock_resp) as mock_req:
            with patch.dict(discord.settings.SERVER, {"TOKEN": "my_token"}, clear=True):
                data = discord.api(
                    "https://discord.com/api/v10/channels/123/messages",
                    method="POST",
                    json_data={"content": "hello"},
                )
                assert data == {"id": "msg1"}
                mock_req.assert_called_once_with(
                    method="POST",
                    url="https://discord.com/api/v10/channels/123/messages",
                    headers={
                        "Authorization": "Bot my_token",
                        "Content-Type": "application/json",
                        "User-Agent": "Helga (https://github.com/bigjust/helga, 2.0.0)",
                    },
                    json={"content": "hello"},
                    params=None,
                )

    def test_api_empty_content(self):
        mock_resp = Mock(status_code=204, content=b"")

        with patch("requests.request", return_value=mock_resp):
            with patch.dict(discord.settings.SERVER, {"API_KEY": "key123"}, clear=True):
                data = discord.api("channels/123/messages/456", method="DELETE")
                assert data == {}

    def test_api_status_error(self):
        mock_resp = Mock(status_code=403, text="Forbidden", content=b"Forbidden")

        with patch("requests.request", return_value=mock_resp):
            with patch.dict(discord.settings.SERVER, {"BOT_TOKEN": "token"}, clear=True):
                with pytest.raises(discord.DiscordError) as exc_info:
                    discord.api("guilds/123")
                assert exc_info.value.status_code == 403
                assert exc_info.value.error == "Forbidden"

    def test_api_request_exception(self):
        with patch("requests.request", side_effect=Exception("Network error")):
            with patch.dict(discord.settings.SERVER, {"BOT_TOKEN": "token"}, clear=True):
                with pytest.raises(discord.DiscordError) as exc_info:
                    discord.api("gateway/bot")
                assert "Network error" in exc_info.value.error

    def test_api_retries_on_429(self):
        limited = Mock(status_code=429, headers={"Retry-After": "0.01"}, content=b"")
        ok = Mock(status_code=200, content=b'{"ok": true}')
        ok.json.return_value = {"ok": True}

        with patch.object(
            discord.requests, "request", side_effect=[limited, ok]
        ) as req, patch.object(discord.time, "sleep") as sleep, patch.dict(
            discord.settings.SERVER, {"BOT_TOKEN": "token"}, clear=True
        ):
            result = discord.api("gateway/bot")

        assert result == {"ok": True}
        assert req.call_count == 2
        sleep.assert_called_once_with(0.01)

    def test_api_gives_up_after_429_retries(self):
        limited = Mock(status_code=429, headers={"Retry-After": "1"}, content=b"")

        with patch.object(
            discord.requests, "request", side_effect=[limited, limited, limited]
        ) as req, patch.object(discord.time, "sleep") as sleep, patch.dict(
            discord.settings.SERVER, {"BOT_TOKEN": "token"}, clear=True
        ):
            with pytest.raises(discord.DiscordError) as exc_info:
                discord.api("gateway/bot")

        assert exc_info.value.status_code == 429
        assert req.call_count == 3
        assert sleep.call_count == 3


class TestFactory:
    def test_factory_success(self):
        with patch.object(
            discord,
            "api",
            side_effect=[{"url": "wss://gateway.discord.gg"}, {"id": "1", "username": "helga"}],
        ):
            factory = discord.Factory()
            assert factory.url == "wss://gateway.discord.gg/?v=10&encoding=json"

    def test_factory_gateway_url_already_has_params(self):
        with patch.object(
            discord,
            "api",
            side_effect=[
                {"url": "wss://gateway.discord.gg/?v=10&encoding=json"},
                {"id": "1", "username": "helga"},
            ],
        ):
            factory = discord.Factory()
            assert factory.url == "wss://gateway.discord.gg/?v=10&encoding=json"

    def test_factory_fallback_on_api_error(self):
        with patch.object(discord, "api", side_effect=Exception("API down")):
            factory = discord.Factory()
            assert factory.url == discord.DEFAULT_GATEWAY_URL

    def test_clientConnectionLost(self):
        with patch.object(discord, "handle_reconnect") as mock_recon:
            with patch.object(discord, "api", return_value={}):
                factory = discord.Factory()
                connector = Mock()
                reason = Mock()
                factory.clientConnectionLost(connector, reason)
                mock_recon.assert_called_with(connector, reason, lost=True)

    def test_clientConnectionFailed(self):
        with patch.object(discord, "handle_reconnect") as mock_recon:
            with patch.object(discord, "api", return_value={}):
                factory = discord.Factory()
                connector = Mock()
                reason = Mock()
                factory.clientConnectionFailed(connector, reason)
                mock_recon.assert_called_with(connector, reason, lost=False)


class TestClient:
    def test_init_defaults(self):
        with patch.object(discord, "task"):
            c = discord.Client()
            assert c.nickname == "helga"
            assert c.user_id == ""

    def test_onOpen(self, client):
        client.onOpen()

    def test_onClose_stops_heartbeat(self, client):
        task_mock = Mock(running=True)
        client._heartbeat_task = task_mock
        client.onClose(True, 1000, "Clean close")
        task_mock.stop.assert_called_once()

    def test_onMessage_bytes(self, client):
        with patch.object(client, "_handle_hello") as mock_hello:
            msg = json.dumps({"op": 10, "d": {"heartbeat_interval": 41250}}).encode("utf-8")
            client.onMessage(msg, True)
            mock_hello.assert_called_once()

    def test_onMessage_invalid_json(self, client):
        client.onMessage("not valid json", False)

    def test_onMessage_sequence_tracking(self, client):
        msg = json.dumps({"op": 0, "s": 42, "t": "READY", "d": {}})
        with patch.object(client, "discord_ready"):
            client.onMessage(msg, False)
            assert client._sequence == 42

    def test_onMessage_heartbeat_ack(self, client):
        client._last_heartbeat_ack = False
        msg = json.dumps({"op": 11})
        client.onMessage(msg, False)
        assert client._last_heartbeat_ack is True

    def test_onMessage_heartbeat_request(self, client):
        msg = json.dumps({"op": 1})
        with patch.object(client, "_send_heartbeat") as mock_hb:
            client.onMessage(msg, False)
            mock_hb.assert_called_once()

    def test_onMessage_reconnect(self, client):
        msg = json.dumps({"op": 7})
        with patch.object(client, "_handle_reconnect_request") as mock_recon:
            client.onMessage(msg, False)
            mock_recon.assert_called_once()

    def test_onMessage_invalid_session(self, client):
        msg = json.dumps({"op": 9, "d": False})
        with patch.object(client, "_handle_invalid_session") as mock_inv:
            client.onMessage(msg, False)
            mock_inv.assert_called_with(False)

    def test_onMessage_unhandled_op(self, client):
        msg = json.dumps({"op": 99})
        client.onMessage(msg, False)

    def test_handle_hello(self, client):
        with patch.object(discord.task, "LoopingCall") as mock_loop:
            with patch.object(client, "_send_identify") as mock_ident:
                client._handle_hello({"heartbeat_interval": 30000})
                assert client._heartbeat_interval == 30.0
                mock_loop.assert_called_once()
                mock_ident.assert_called_once()

    def test_handle_hello_stops_existing_task(self, client):
        existing_task = Mock(running=True)
        client._heartbeat_task = existing_task
        with patch.object(discord.task, "LoopingCall"):
            with patch.object(client, "_send_identify"):
                client._handle_hello({"heartbeat_interval": 30000})
                existing_task.stop.assert_called_once()

    def test_send_heartbeat(self, client):
        client._sequence = 100
        with patch.object(client, "sendMessage") as mock_send:
            client._send_heartbeat()
            assert client._last_heartbeat_ack is False
            mock_send.assert_called_once()
            sent_data = json.loads(mock_send.call_args[0][0].decode("utf-8"))
            assert sent_data == {"op": 1, "d": 100}

    def test_send_identify(self, client):
        with patch.dict(discord.settings.SERVER, {"BOT_TOKEN": "bot_token_123"}, clear=True):
            with patch.object(client, "sendMessage") as mock_send:
                client._send_identify()
                mock_send.assert_called_once()
                sent_data = json.loads(mock_send.call_args[0][0].decode("utf-8"))
                assert sent_data["op"] == 2
                assert sent_data["d"]["token"] == "bot_token_123"
                assert sent_data["d"]["intents"] == discord.DEFAULT_INTENTS

    def test_handle_reconnect_request(self, client):
        with patch.object(client, "sendClose") as mock_close:
            client._handle_reconnect_request()
            mock_close.assert_called_with(1000, "Discord requested reconnect")

    def test_handle_invalid_session_resumable(self, client):
        with patch.object(client, "_send_identify") as mock_ident:
            client._handle_invalid_session(True)
            mock_ident.assert_called_once()

    def test_handle_invalid_session_non_resumable(self, client):
        with patch.object(discord.reactor, "callLater") as mock_call_later:
            client._handle_invalid_session(False)
            assert client._sequence is None
            assert client.session_id is None
            mock_call_later.assert_called_with(1, client._send_identify)

    def test_discord_ready(self, client):
        data = {
            "session_id": "sess_123",
            "user": {
                "id": "9999",
                "username": "helgabot",
            },
        }
        with patch.object(discord.smokesignal, "emit") as mock_emit:
            client.discord_ready(data)
            assert client.session_id == "sess_123"
            assert client.user_id == "9999"
            assert client.nickname == "helgabot"
            assert client._user_names["9999"] == "helgabot"
            assert discord.settings.COMMAND_PREFIX_BOTNICK == "@?helgabot"
            mock_emit.assert_called_with("signon", client)

    def test_discord_guild_create(self, client):
        data = {
            "channels": [
                {"id": "101", "name": "general", "type": 0},
                {"id": "102", "name": "random", "type": 0},
                {"id": "103", "name": "voice", "type": 2},  # voice channel ignored for text
            ],
            "members": [
                {"user": {"id": "201", "username": "alice"}},
                {"user": {"id": "202", "username": "bob"}},
            ],
        }
        client.discord_guild_create(data)
        assert client._channel_names["101"] == "general"
        assert client._channel_names["102"] == "random"
        assert "#general" in client.channels
        assert "#random" in client.channels
        assert client._user_names["201"] == "alice"
        assert client._user_names["202"] == "bob"

    def test_discord_channel_create(self, client):
        data = {"id": "104", "name": "announcements", "type": 0}
        with patch.object(discord.smokesignal, "emit") as mock_emit:
            client.discord_channel_create(data)
            assert client._channel_names["104"] == "announcements"
            assert "#announcements" in client.channels
            mock_emit.assert_called_with("join", client, "#announcements")

    def test_discord_channel_update(self, client):
        data = {"id": "104", "name": "announcements-renamed", "type": 0}
        client.discord_channel_update(data)
        assert client._channel_names["104"] == "announcements-renamed"
        assert "#announcements-renamed" in client.channels

    def test_discord_channel_delete(self, client):
        client._channel_names["104"] = "announcements"
        client.channels.add("#announcements")

        with patch.object(discord.smokesignal, "emit") as mock_emit:
            client.discord_channel_delete({"id": "104", "name": "announcements"})
            assert "104" not in client._channel_names
            assert "#announcements" not in client.channels
            mock_emit.assert_called_with("left", client, "#announcements")

    def test_discord_guild_member_add(self, client):
        data = {
            "guild_id": "guild_1",
            "user": {"id": "301", "username": "charlie"},
        }
        with patch.object(discord.smokesignal, "emit") as mock_emit:
            client.discord_guild_member_add(data)
            assert client._user_names["301"] == "charlie"
            mock_emit.assert_called_with("user_joined", client, "charlie", "guild_1")

    def test_discord_guild_member_remove(self, client):
        data = {
            "guild_id": "guild_1",
            "user": {"id": "301", "username": "charlie"},
        }
        with patch.object(discord.smokesignal, "emit") as mock_emit:
            client.discord_guild_member_remove(data)
            mock_emit.assert_called_with("user_left", client, "charlie", "guild_1")

    def test_discord_message_create_ignore_self(self, client):
        client.user_id = "123456789"
        client.nickname = "helga"
        data = {
            "author": {"id": "123456789", "username": "helga"},
            "content": "hello myself",
            "channel_id": "101",
            "guild_id": "guild_1",
        }
        with patch.object(discord.registry, "process") as mock_proc:
            client.discord_message_create(data)
            mock_proc.assert_not_called()

    def test_discord_message_create_guild_channel(self, client):
        client._channel_names["101"] = "general"
        data = {
            "author": {"id": "201", "username": "alice"},
            "content": "helga ping",
            "channel_id": "101",
            "guild_id": "guild_1",
        }
        with patch.object(
            discord.registry, "preprocess", return_value=("#general", "alice", "helga ping")
        ):
            with patch.object(discord.registry, "process", return_value=["pong"]):
                with patch.object(client, "msg") as mock_msg:
                    client.discord_message_create(data)
                    assert client.last_message["#general"]["alice"] == "helga ping"
                    mock_msg.assert_called_with("#general", "pong")

    def test_discord_message_create_direct_message(self, client):
        data = {
            "author": {"id": "201", "username": "alice"},
            "content": "helga ping",
            "channel_id": "dm_channel_999",
        }
        with patch.object(
            discord.registry, "preprocess", return_value=("alice", "alice", "helga ping")
        ):
            with patch.object(discord.registry, "process", return_value=["pong"]):
                with patch.object(client, "msg") as mock_msg:
                    client.discord_message_create(data)
                    assert client.last_message["alice"]["alice"] == "helga ping"
                    assert client._dm_channels["alice"] == "dm_channel_999"
                    mock_msg.assert_called_with("alice", "pong")

    def test_me(self, client):
        with patch.object(client, "msg") as mock_msg:
            client.me("#general", "waves")
            mock_msg.assert_called_with("#general", "_waves_")

    def test_msg_channel_name(self, client):
        client._channel_names["101"] = "general"
        with patch.object(client, "_send_message") as mock_send:
            client.msg("#general", "hello world")
            mock_send.assert_called_with("101", "hello world")

    def test_msg_dm_cached(self, client):
        client._dm_channels["alice"] = "dm_101"
        with patch.object(client, "_send_message") as mock_send:
            client.msg("alice", "hello alice")
            mock_send.assert_called_with("dm_101", "hello alice")

    def test_msg_dm_uncached_calls_reactor(self, client):
        with patch.object(discord.reactor, "callLater") as mock_call:
            client.msg("bob", "hello bob")
            mock_call.assert_called_with(0, client._async_msg_user, "bob", "hello bob")

    def test_async_msg_user_success(self, client):
        client._user_names["201"] = "alice"
        with patch.object(discord, "api", return_value={"id": "dm_channel_201"}):
            with patch.object(client, "_send_message") as mock_send:
                client._async_msg_user("alice", "hello alice")
                assert client._dm_channels["alice"] == "dm_channel_201"
                mock_send.assert_called_with("dm_channel_201", "hello alice")

    def test_async_msg_user_unknown_user(self, client):
        with patch.object(discord, "api") as mock_api:
            client._async_msg_user("unknown_user", "hello")
            mock_api.assert_not_called()

    def test_async_msg_user_api_error(self, client):
        client._user_names["201"] = "alice"
        with patch.object(discord, "api", side_effect=Exception("API Error")):
            client._async_msg_user("alice", "hello alice")

    def test_send_message_single_chunk(self, client):
        with patch.object(discord, "api") as mock_api:
            client._send_message("101", "short message")
            mock_api.assert_called_once_with(
                "channels/101/messages",
                method="POST",
                json_data={"content": "short message"},
            )

    def test_handle_dispatch_none_event(self, client):
        client._handle_dispatch(None, {})

    def test_handle_dispatch_exception(self, client):
        with patch.object(client, "discord_ready", side_effect=Exception("Failed")):
            client._handle_dispatch("READY", {})

    def test_handle_dispatch_unhandled_event(self, client):
        client._handle_dispatch("UNKNOWN_EVENT_TYPE", {})

    def test_msg_channel_unresolved(self, client):
        with patch.object(client, "_send_message") as mock_send:
            client.msg("#unknown_channel", "hello")
            mock_send.assert_called_with("unknown_channel", "hello")

    def test_msg_channel_id_as_channel_name(self, client):
        client._channel_names["101"] = "general"
        with patch.object(client, "_send_message") as mock_send:
            client.msg("101", "hello")
            mock_send.assert_called_with("101", "hello")

    def test_send_message_multi_chunk_no_newline(self, client):
        long_message = "A" * 3500
        with patch.object(discord, "api") as mock_api:
            client._send_message("101", long_message)
            assert mock_api.call_count == 2

    def test_send_message_api_exception(self, client):
        with patch.object(discord, "api", side_effect=Exception("Network fail")):
            client._send_message("101", "hello")

    def test_join_and_leave(self, client):
        join_res = client.join("#general")
        assert "Bots cannot join" in join_res

        leave_res = client.leave("#general")
        assert "Bots cannot leave" in leave_res

    def test_get_channel_name_and_id(self, client):
        client._channel_names["101"] = "general"
        assert client._get_channel_name("101") == "general"
        assert client._get_channel_name("999") == ""
        assert client._get_channel_id("general") == "101"
        assert client._get_channel_id("#general") == "101"
        assert client._get_channel_id("nonexistent") is None

    def test_get_user_name_and_id(self, client):
        client._user_names["201"] = "alice"
        assert client._get_user_name("201") == "alice"
        assert client._get_user_name("999") == ""
        assert client._get_user_id("alice") == "201"
        assert client._get_user_id("@alice") == "201"
        assert client._get_user_id("nonexistent") is None

    def test_parse_incoming_message(self, client):
        client._user_names["201"] = "alice"
        client._channel_names["101"] = "general"

        message = "<@201> check out <#101> &lt;test&gt;"
        parsed = client._parse_incoming_message(message)
        assert parsed == "@alice check out #general <test>"

        # Nickname mention <@!id>
        message2 = "<@!201> hi"
        assert client._parse_incoming_message(message2) == "@alice hi"

    def test_parse_incoming_message_mention_from_payload(self, client):
        # Mentions resolved from the message payload even when not cached
        message = "<@999> hi"
        result = client._parse_incoming_message(message, [{"id": "999", "username": "carol"}])
        assert result == "@carol hi"

    def test_parse_incoming_message_unknown_mention(self, client):
        # Unknown mentions are left untouched
        assert client._parse_incoming_message("<@123> hi") == "<@123> hi"

    def test_discord_message_create_ignores_other_bots(self, client):
        data = {
            "author": {"id": "b1", "username": "some-other-bot", "bot": True},
            "content": "hello",
            "channel_id": "101",
            "guild_id": "guild_1",
        }
        with patch.object(discord.registry, "process") as mock_proc:
            client.discord_message_create(data)
            mock_proc.assert_not_called()

    def test_async_msg_user_uses_cached_dm(self, client):
        client._user_names["201"] = "alice"
        client._dm_channels["alice"] = "dm_cached"
        with patch.object(discord, "api") as mock_api:
            with patch.object(client, "_send_message") as mock_send:
                client._async_msg_user("alice", "hello")
                # DM open endpoint must not be touched when the channel is cached
                for call in mock_api.call_args_list:
                    assert "users/@me/channels" not in call.args[0]
                mock_send.assert_called_with("dm_cached", "hello")

    def test_sanitize_escapes_mass_mentions(self, client):
        assert "@\u200beveryone" in client._sanitize("hi @everyone")
        assert "@\u200bhere" in client._sanitize("hi @here")

    def test_msg_sanitizes_before_send(self, client):
        client._channel_names["101"] = "general"
        with patch.object(client, "_send_message") as mock_send:
            client.msg("#general", "watch out @everyone")
            args = mock_send.call_args[0]
            assert "@everyone" not in args[1]


class TestSessionResume:
    def _connected_client(self, session_id, sequence):
        factory = Mock(session_id=session_id, sequence=sequence)
        with patch.object(discord, "task"):
            c = discord.Client({"id": "1", "username": "helga"}, factory)
        return c, factory

    def test_hello_resumes_existing_session(self):
        c, factory = self._connected_client("sess-1", 42)
        with patch.dict(discord.settings.SERVER, {"BOT_TOKEN": "tok"}, clear=True):
            with patch.object(c, "sendMessage") as send:
                c._handle_hello({"heartbeat_interval": 40000})
        payload = json.loads(send.call_args[0][0].decode("utf-8"))
        assert payload["op"] == 6
        assert payload["d"]["session_id"] == "sess-1"
        assert payload["d"]["seq"] == 42
        assert payload["d"]["token"] == "tok"

    def test_hello_identifies_when_no_session(self):
        c, factory = self._connected_client(None, None)
        with patch.object(c, "_send_identify") as identify:
            c._handle_hello({"heartbeat_interval": 40000})
            identify.assert_called_once()

    def test_ready_stores_resume_state(self):
        c, factory = self._connected_client(None, None)
        c._sequence = 7
        c.discord_ready({"session_id": "sess-9", "user": {"id": "1", "username": "helga"}})
        assert factory.session_id == "sess-9"
        assert factory.sequence == 7

    def test_invalid_session_resumable_resumes(self):
        c, factory = self._connected_client("sess-1", 42)
        with patch.object(c, "sendMessage") as send:
            c._handle_invalid_session(True)
        payload = json.loads(send.call_args[0][0].decode("utf-8"))
        assert payload["op"] == 6

    def test_invalid_session_not_resumable_clears(self):
        c, factory = self._connected_client("sess-1", 42)
        with patch.object(discord.reactor, "callLater"):
            c._handle_invalid_session(False)
        assert factory.session_id is None
        assert factory.sequence is None
        assert c.session_id is None
        assert c._sequence is None

    def test_discord_resumed_emits_signon(self, client):
        with patch.object(discord.smokesignal, "emit") as emit:
            client.discord_resumed({})
        emit.assert_called_with("signon", client)


class TestDeduplication:
    def test_message_create_deduplicates(self, client):
        client.id = "1"
        data = {
            "id": "dup-1",
            "author": {"id": "201", "username": "alice"},
            "content": "hello",
            "channel_id": "101",
            "guild_id": "g1",
        }
        with patch.object(discord.registry, "process", return_value=[]) as process:
            client.discord_message_create(data)
            client.discord_message_create(data)
            process.assert_called_once()

    def test_processed_messages_bounded(self, client):
        with patch.object(discord.registry, "process", return_value=[]):
            for i in range(1005):
                client.discord_message_create(
                    {
                        "id": str(i),
                        "author": {"id": "201", "username": "alice"},
                        "content": "x",
                        "channel_id": "101",
                        "guild_id": "g1",
                    }
                )
        assert len(client._processed_messages) <= 1000
        # A brand-new message is still processed after the cap is hit
        data = {
            "id": "fresh-1",
            "author": {"id": "201", "username": "alice"},
            "content": "y",
            "channel_id": "101",
            "guild_id": "g1",
        }
        with patch.object(discord.registry, "process", return_value=[]) as process:
            client.discord_message_create(data)
            process.assert_called_once()


class TestChannelLogging:
    def test_log_channel_message_enabled(self, client):
        with patch.object(
            client, "get_channel_logger", return_value=Mock()
        ) as get_logger, patch.object(discord.settings, "CHANNEL_LOGGING", True):
            client.log_channel_message("#general", "alice", "hi")
        get_logger.assert_called_with("#general")
        get_logger.return_value.info.assert_called_with("hi", extra={"nick": "alice"})

    def test_log_channel_message_disabled(self, client):
        with patch.object(client, "get_channel_logger") as get_logger, patch.object(
            discord.settings, "CHANNEL_LOGGING", False
        ):
            client.log_channel_message("#general", "alice", "hi")
        get_logger.assert_not_called()

    def test_message_create_logs_public_channel_traffic(self, client):
        client.id = "1"
        client._channel_names["101"] = "general"
        data = {
            "id": "m1",
            "author": {"id": "201", "username": "alice"},
            "content": "hello",
            "channel_id": "101",
            "guild_id": "g1",
        }
        with patch.object(client, "get_channel_logger", return_value=Mock()) as get_logger:
            with patch.object(discord.settings, "CHANNEL_LOGGING", True):
                with patch.object(
                    discord.registry,
                    "preprocess",
                    side_effect=lambda c, ch, u, m: (ch, u, m),
                ):
                    with patch.object(discord.registry, "process", return_value=["pong"]):
                        client.discord_message_create(data)
        # incoming message and helga's response are both logged
        get_logger.return_value.info.assert_any_call("hello", extra={"nick": "alice"})
        get_logger.return_value.info.assert_any_call("pong", extra={"nick": "helga"})

    def test_message_create_does_not_log_dm(self, client):
        data = {
            "id": "dm-1",
            "author": {"id": "201", "username": "alice"},
            "content": "hi",
            "channel_id": "dm1",
        }
        with patch.object(client, "log_channel_message") as log_mock, patch.object(
            discord.registry, "preprocess", side_effect=lambda c, ch, u, m: (ch, u, m)
        ), patch.object(discord.registry, "process", return_value=[]):
            client.discord_message_create(data)
        log_mock.assert_not_called()
