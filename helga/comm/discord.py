"""
Twisted protocol and communication implementations for Discord
"""

import contextlib
import html
import json
import re
import sys
import time
from functools import partial

import requests
import smokesignal
from autobahn.twisted.websocket import WebSocketClientFactory, WebSocketClientProtocol
from twisted.internet import reactor, task, threads

from helga import log, settings
from helga.comm.base import BaseClient, handle_reconnect
from helga.plugins import registry

logger = log.getLogger(__name__)

#: Discord REST API version and base URL used for all HTTP requests
GATEWAY_VERSION = 10
DISCORD_API_BASE = f"https://discord.com/api/v{GATEWAY_VERSION}/"

#: Fallback gateway used if the gateway URL cannot be fetched at startup
DEFAULT_GATEWAY_URL = f"wss://gateway.discord.gg/?v={GATEWAY_VERSION}&encoding=json"

#: Discord message content limit; longer messages must be split into chunks
DISCORD_MESSAGE_LIMIT = 2000

#: Gateway intents. See https://discord.com/developers/docs/topics/gateway#gateway-intents
INTENT_GUILDS = 1 << 0
INTENT_GUILD_MEMBERS = 1 << 1
INTENT_GUILD_MESSAGES = 1 << 9
INTENT_DIRECT_MESSAGES = 1 << 12
INTENT_MESSAGE_CONTENT = 1 << 15

#: The default set of intents requested on identify. Note that ``INTENT_GUILD_MEMBERS``
#: and ``INTENT_MESSAGE_CONTENT`` are privileged intents that must be explicitly enabled
#: for the bot application in the Discord developer portal.
DEFAULT_INTENTS = (
    INTENT_GUILDS
    | INTENT_GUILD_MEMBERS
    | INTENT_GUILD_MESSAGES
    | INTENT_DIRECT_MESSAGES
    | INTENT_MESSAGE_CONTENT
)

#: Channel types that are treated as text channels helga can talk in. See
#: https://discord.com/developers/docs/resources/channel#channel-object-channel-types
TEXT_CHANNEL_TYPES = (0, 5)  # GUILD_TEXT, GUILD_ANNOUNCEMENT

# Gateway opcodes. See https://discord.com/developers/docs/topics/opcodes-and-status-codes
OP_DISPATCH = 0
OP_HEARTBEAT = 1
OP_IDENTIFY = 2
OP_RECONNECT = 7
OP_INVALID_SESSION = 9
OP_HELLO = 10
OP_HEARTBEAT_ACK = 11


def api(endpoint, method="GET", json_data=None, params=None, token=None):
    """
    Make an HTTP request to the Discord REST API.

    :param endpoint: API endpoint path (e.g. 'gateway/bot' or 'channels/123/messages'),
                     or a full URL
    :param method: HTTP method ('GET', 'POST', 'DELETE', etc.)
    :param json_data: JSON payload dictionary for POST/PATCH requests
    :param params: Query parameters dictionary for GET requests
    :param token: Optional bot token; defaults to token from settings
    :returns: Response parsed as JSON (or empty dict if no content)
    :raises DiscordError: If the HTTP request fails or returns status >= 400
    """
    token = (
        token
        or settings.SERVER.get("BOT_TOKEN")
        or settings.SERVER.get("TOKEN")
        or settings.SERVER.get("API_KEY")
    )

    headers = {
        "Authorization": f"Bot {token}",
        "Content-Type": "application/json",
        "User-Agent": "Helga (https://github.com/bigjust/helga, 2.0.0)",
    }

    if endpoint.startswith("http://") or endpoint.startswith("https://"):
        url = endpoint
    else:
        url = DISCORD_API_BASE + endpoint.lstrip("/")

    logger.debug("Discord API request: %s %s -> %s", method, url, json_data)

    # Bounded retry on 429 rate limits, honoring Discord's Retry-After header.
    # Calls run inside deferToThread, so waiting here sleeps a worker thread,
    # not the reactor.
    for attempt in range(3):
        try:
            response = requests.request(
                method=method.upper(),
                url=url,
                headers=headers,
                json=json_data,
                params=params,
            )
        except Exception as e:
            raise DiscordError(api=endpoint, error=str(e)) from e

        if response.status_code == 429:
            try:
                retry_after = float(response.headers.get("Retry-After", "1"))
            except (TypeError, ValueError):
                retry_after = 1.0
            logger.warning("Rate limited by Discord, retrying in %s seconds", retry_after)
            time.sleep(retry_after)
            continue

        if response.status_code >= 400:
            raise DiscordError(api=endpoint, status_code=response.status_code, error=response.text)

        if response.content:
            return response.json()
        return {}

    raise DiscordError(
        api=endpoint, status_code=429, error="Rate limited by Discord (retries exhausted)"
    )


class Factory(WebSocketClientFactory):
    """
    WebSocket client factory for the Discord Gateway.
    Fetches the gateway URL (falling back to a default) and the bot's own user
    object, so the client can identify itself before the READY event arrives.
    """

    def __init__(self):
        logger.info("Initiating Discord gateway request")
        gateway_url = DEFAULT_GATEWAY_URL
        bot_user = None

        try:
            gateway_data = api("gateway/bot")
            url = gateway_data.get("url")
            if url:
                if not url.endswith(f"/?v={GATEWAY_VERSION}&encoding=json"):
                    gateway_url = f"{url.rstrip('/')}/?v={GATEWAY_VERSION}&encoding=json"
                else:
                    gateway_url = url
        except Exception as e:
            logger.warning("Failed to fetch Discord gateway URL, using default: %s", e)

        try:
            bot_user = api("users/@me")
        except Exception as e:
            logger.warning("Failed to fetch Discord bot user info: %s", e)

        self.protocol = partial(Client, bot_user, self)

        #: Gateway session state kept across reconnects so a fresh Client can
        #: RESUME instead of re-identifying (see _send_resume)
        self.session_id = None
        self.sequence = None

        logger.info("Creating WebSocketClientFactory with %s", gateway_url)
        WebSocketClientFactory.__init__(self, url=gateway_url)

    def clientConnectionLost(self, connector, reason):
        """
        Handler for when the Discord gateway connection is lost.
        """
        logger.info("Connection to server lost: %s", reason)
        handle_reconnect(connector, reason, lost=True)

    def clientConnectionFailed(self, connector, reason):
        """
        Handler for when the Discord gateway connection fails.
        """
        logger.warning("Connection to server failed: %s", reason)
        handle_reconnect(connector, reason, lost=False)


class Client(WebSocketClientProtocol, BaseClient):  # type: ignore[misc]
    """
    Discord Gateway WebSocket protocol client for Helga.
    """

    def __init__(self, bot_user=None, factory=None, *a, **kw):
        BaseClient.__init__(self)

        self.bot_user = bot_user or {}
        #: The Factory that created us; holds session state across reconnects
        self._factory = factory
        self.nickname = self.bot_user.get("username", getattr(settings, "NICK", "helga"))
        self.user_id = str(self.bot_user.get("id", ""))
        self.session_id = None
        self._sequence = None
        self._heartbeat_task = None
        self._heartbeat_interval = None
        self._last_heartbeat_ack = True

        # Maps of channel/user id -> name
        self._channel_names = {}  # channel_id -> channel_name
        self._user_names = {}  # user_id -> username
        self._dm_channels = {}  # user_name_or_id -> dm_channel_id
        #: Recent message ids, to drop duplicate MESSAGE_CREATE events the
        #: gateway can deliver after a reconnect
        self._processed_messages = set()

        if self.user_id and self.nickname:
            self._user_names[self.user_id] = self.nickname

        settings.COMMAND_PREFIX_BOTNICK = "@?" + self.nickname

        WebSocketClientProtocol.__init__(self, *a, **kw)

    def onOpen(self):
        logger.info("Connected to Discord Gateway WebSocket")

    def onClose(self, wasClean, code, reason):
        """
        Stop the heartbeat loop when the gateway connection closes.
        """
        logger.info("Discord Gateway WebSocket closed (code=%s, reason=%s)", code, reason)
        if self._heartbeat_task is not None and self._heartbeat_task.running:
            self._heartbeat_task.stop()

    def onMessage(self, payload, isBinary):
        """
        Receive a raw message from the Discord gateway WebSocket. The message is a JSON
        string containing an opcode ("op"), and for dispatched events, an event name
        ("t") and sequence number ("s"). Dispatched events are routed to a similarly
        named "discord_" function, if one exists. For example, a dispatched event of
        type "MESSAGE_CREATE" will call ``self.discord_message_create()``.
        """
        if isinstance(payload, bytes):
            payload = payload.decode("utf-8")

        try:
            data = json.loads(payload)
        except (ValueError, TypeError) as e:
            logger.error("Error parsing WebSocket message %s: %s", payload, e)
            return

        op = data.get("op")
        d = data.get("d")
        s = data.get("s")
        t = data.get("t")

        if s is not None:
            self._sequence = s
            if self._factory is not None:
                self._factory.sequence = s

        if op == OP_HELLO:
            self._handle_hello(d)
        elif op == OP_HEARTBEAT_ACK:
            self._last_heartbeat_ack = True
        elif op == OP_HEARTBEAT:
            self._send_heartbeat()
        elif op == OP_RECONNECT:
            self._handle_reconnect_request()
        elif op == OP_INVALID_SESSION:
            self._handle_invalid_session(d)
        elif op == OP_DISPATCH:
            self._handle_dispatch(t, d)
        else:
            logger.debug("No implementation for opcode %r", op)

    def _handle_hello(self, data):
        """
        Handler for the gateway HELLO opcode. Starts the heartbeat loop and
        identifies this connection with the gateway.

        :param data: dict from JSON received in the HELLO payload
        """
        interval_ms = data.get("heartbeat_interval", 41250) if isinstance(data, dict) else 41250
        self._heartbeat_interval = interval_ms / 1000.0

        if self._heartbeat_task is not None and self._heartbeat_task.running:
            self._heartbeat_task.stop()

        self._heartbeat_task = task.LoopingCall(self._send_heartbeat)
        self._heartbeat_task.start(self._heartbeat_interval, now=False)

        if self._factory is not None and self._factory.session_id:
            self._send_resume()
        else:
            self._send_identify()

    def _send_heartbeat(self):
        """
        Send an Opcode 1 Heartbeat to the gateway. If the previous heartbeat
        went unacknowledged, the connection is presumed dead and is dropped so
        the factory reconnect logic can re-establish it.
        """
        if not self._last_heartbeat_ack:
            logger.warning("Discord heartbeat ACK not received, dropping connection")
            self.sendClose(1000, "Heartbeat not acknowledged")
            return

        self._last_heartbeat_ack = False
        self.sendMessage(json.dumps({"op": OP_HEARTBEAT, "d": self._sequence}).encode("utf-8"))

    def _token(self):
        """
        Resolve the bot token from settings.
        """
        return (
            settings.SERVER.get("BOT_TOKEN")
            or settings.SERVER.get("TOKEN")
            or settings.SERVER.get("API_KEY")
        )

    def _send_identify(self):
        """
        Sends the IDENTIFY payload to the gateway, authenticating this connection
        using the configured bot token.
        """
        token = self._token()
        intents = getattr(settings, "DISCORD_INTENTS", DEFAULT_INTENTS)

        self.sendMessage(
            json.dumps(
                {
                    "op": OP_IDENTIFY,
                    "d": {
                        "token": token,
                        "intents": intents,
                        "properties": {
                            "os": sys.platform,
                            "browser": "helga",
                            "device": "helga",
                        },
                    },
                }
            ).encode("utf-8")
        )

    def _send_resume(self):
        """
        Send an Opcode 6 RESUME payload to the gateway, continuing the session
        identified by the factory-held session state. Falls back to IDENTIFY if
        there is nothing to resume.
        """
        if self._factory is None or not self._factory.session_id:
            return self._send_identify()

        payload = {
            "op": 6,
            "d": {
                "token": self._token(),
                "session_id": self._factory.session_id,
                "seq": self._factory.sequence,
            },
        }
        logger.info("Resuming Discord session %s", self._factory.session_id)
        self.sendMessage(json.dumps(payload).encode("utf-8"))

    def _handle_reconnect_request(self):
        """
        Handle Opcode 7 Reconnect request from Discord Gateway.
        """
        logger.info("Discord requested reconnect")
        self.sendClose(1000, "Discord requested reconnect")

    def _handle_invalid_session(self, resumable):
        """
        Handle Opcode 9 Invalid Session from the gateway. If the session is
        resumable, re-identify immediately; otherwise reset our state and
        re-identify after a short delay.
        """
        logger.warning("Discord session is invalid (resumable=%s)", resumable)
        if resumable:
            # Session can be resumed; if we never had one, identify fresh
            self._send_resume()
        else:
            self._sequence = None
            self.session_id = None
            if self._factory is not None:
                self._factory.session_id = None
                self._factory.sequence = None
            reactor.callLater(1, self._send_identify)

    def _handle_dispatch(self, event_type, data):
        """
        Dispatch Opcode 0 events to matching discord_<event_type> methods.
        """
        if not event_type:
            return

        method_name = f"discord_{event_type.lower()}"

        try:
            getattr(self, method_name)(data)
        except AttributeError:
            logger.debug("No implementation for %r", method_name)
        except Exception:
            logger.exception("Failed to handle method call to %s", method_name)

    def _cache_channel(self, channel):
        """
        Caches a single channel object's id/name pair, and if it is a text
        channel, tracks it as a known channel.

        :param channel: a Discord channel object dict
        """
        channel_id = channel.get("id")
        name = channel.get("name")

        if not channel_id or not name:
            return

        self._channel_names[channel_id] = name

        if channel.get("type") in TEXT_CHANNEL_TYPES:
            self.channels.add(f"#{name}")

    def discord_ready(self, data):
        """
        Called when the client has successfully identified with the gateway.
        Sends the ``signon`` signal (see :ref:`plugins.signals`)
        """
        self.session_id = data.get("session_id")
        user = data.get("user", {})
        self.user_id = str(user.get("id", self.user_id))
        self.nickname = user.get("username", self.nickname)

        if self.user_id and self.nickname:
            self._user_names[self.user_id] = self.nickname

        # Similarly to Slack, it's simpler to override the user's
        # COMMAND_PREFIX_BOTNICK setting here to reduce manual configuration,
        # since Discord uses "@ mentions" syntax for addressing users.
        settings.COMMAND_PREFIX_BOTNICK = "@?" + self.nickname

        # Store resume state on the factory so a reconnecting Client can resume
        if self._factory is not None:
            self._factory.session_id = self.session_id
            self._factory.sequence = self._sequence

        logger.info("Signed on to Discord as %s", self.nickname)
        smokesignal.emit("signon", self)

    def discord_resumed(self, data):
        """
        Called when the gateway confirms a resumed session (RESUMED event).
        """
        logger.info("Discord session resumed")
        smokesignal.emit("signon", self)

    def discord_guild_create(self, data):
        """
        Called when the gateway sends guild information, generally right after
        signon for every guild (server) the bot is a member of. Caches channel
        and member names.
        """
        for channel in data.get("channels", []) or []:
            self._cache_channel(channel)

        for member in data.get("members", []) or []:
            user = member.get("user") or {}
            if user.get("id"):
                self._user_names[user["id"]] = user.get("username", "")

    def discord_channel_create(self, data):
        """
        Triggers when a new channel is created.
        """
        self._cache_channel(data)
        if data.get("name") and data.get("type") in TEXT_CHANNEL_TYPES:
            smokesignal.emit("join", self, f"#{data['name']}")

    def discord_channel_update(self, data):
        """
        Triggers when a channel is renamed or otherwise updated.
        """
        self._cache_channel(data)

    def discord_channel_delete(self, data):
        """
        Triggers when a channel is deleted.
        """
        channel_id = data.get("id")
        name = self._channel_names.pop(channel_id, None) or data.get("name")
        if name:
            self.channels.discard(f"#{name}")
            smokesignal.emit("left", self, f"#{name}")

    def discord_guild_member_add(self, data):
        """
        Caches the username of a newly added guild member.
        """
        user = data.get("user") or {}
        if user.get("id"):
            self._user_names[user["id"]] = user.get("username", "")
        guild_id = data.get("guild_id", "")
        smokesignal.emit("user_joined", self, user.get("username", ""), guild_id)

    def discord_guild_member_remove(self, data):
        """
        Emits a signal when a guild member leaves.
        """
        user = data.get("user") or {}
        guild_id = data.get("guild_id", "")
        smokesignal.emit("user_left", self, user.get("username", ""), guild_id)

    def discord_message_create(self, data):
        """
        Handler for an incoming Discord message create event. This method allows
        the plugin manager to send the message to all registered plugins. Should
        the plugin manager yield a response, it will be sent back over Discord.
        """
        # Deduplicate: Discord gateway may send duplicate MESSAGE_CREATE events
        message_id = str(data.get("id", ""))
        if message_id:
            if message_id in self._processed_messages:
                return
            self._processed_messages.add(message_id)
            if len(self._processed_messages) > 1000:
                self._processed_messages.pop()

        author = data.get("author") or {}
        author_id = str(author.get("id", ""))
        author_name = author.get("username", "")

        if author_id and author_name:
            self._user_names[author_id] = author_name

        # Ignore our own messages (infinite reply loop), and other bots' messages
        # (bot-to-bot chatter we should not participate in).
        if author.get("bot") or author_id == self.user_id or author_name == self.nickname:
            return

        channel_id = str(data.get("channel_id", ""))
        guild_id = data.get("guild_id")

        if guild_id:
            channel_name = self._get_channel_name(channel_id)
            channel = f"#{channel_name}" if channel_name else channel_id
        else:
            # Direct message; respond back to the sending user and remember the
            # DM channel so we don't have to re-open it via the API
            channel = author_name
            self._dm_channels[author_name] = channel_id
            if author_id:
                self._dm_channels[author_id] = channel_id

        message = self._parse_incoming_message(data.get("content", ""), data.get("mentions"))

        # Log public channel messages if channel logging is enabled
        if channel.startswith("#"):
            self.log_channel_message(channel, author_name, message)

        # Some things should go first
        with contextlib.suppress(TypeError, ValueError):
            channel, author_name, message = registry.preprocess(self, channel, author_name, message)

        # Update last message
        self.last_message[channel][author_name] = message

        responses = registry.process(self, channel, author_name, message)

        if responses:
            joined = "\n".join(responses)
            self.msg(channel, joined)
            if channel.startswith("#"):
                self.log_channel_message(channel, self.nickname, joined)

    def me(self, channel, message):
        """
        Send an italicized message over Discord to the specified channel, similar
        in spirit to an IRC "/me" action, since Discord has no native concept of
        action messages.
        """
        return self.msg(channel, f"_{message}_")

    def msg(self, channel, message):
        """
        Send a message over Discord to the specified channel.

        :param channel: The Discord channel to send the message to (eg "#general",
                        by name or id). A channel not prefixed by a '#' is sent as
                        a direct message to a user with that name.
        :param message: The message to send
        """
        message = self._sanitize(message)

        logger.debug("[-->] %s - %s", channel, message)

        if channel.startswith("#"):
            channel_id = self._get_channel_id(channel)
            if channel_id:
                return self._send_message(channel_id, message)
            # Unknown name: send to the raw id, which is the best we can do
            return self._send_message(channel.lstrip("#"), message)
        elif channel in self._dm_channels:
            return self._send_message(self._dm_channels[channel], message)
        elif self._get_channel_name(channel):
            return self._send_message(channel, message)
        else:
            reactor.callLater(0, self._async_msg_user, channel, message)

    def _async_msg_user(self, user, message):
        """
        Sends a direct message to a user, opening a DM channel with them first if
        needed. DM channels are cached by both username and user id.

        The REST call runs in a worker thread so the reactor is not blocked.
        """
        user_id = self._get_user_id(user) or (user if user.isdigit() else None)
        if not user_id:
            logger.error("Cannot find Discord user ID for %s", user)
            return

        dm_channel_id = self._dm_channels.get(user) or self._dm_channels.get(user_id)
        if dm_channel_id:
            return self._send_message(dm_channel_id, message)

        def _opened(data):
            try:
                new_channel_id = str(data["id"])
            except (KeyError, TypeError):
                logger.error("Discord DM open returned no channel id for %s", user)
                return
            self._dm_channels[user] = new_channel_id
            self._dm_channels[user_id] = new_channel_id
            self._send_message(new_channel_id, message)

        def _failed(failure):
            logger.error("Failed to open DM channel with user %s: %s", user, failure.value)

        d = threads.deferToThread(
            api, "users/@me/channels", method="POST", json_data={"recipient_id": user_id}
        )
        d.addCallback(_opened).addErrback(_failed)

    def _send_message(self, channel_id, message):
        """
        Send message text to a Discord channel via REST API, splitting it into
        chunks at newline boundaries if it exceeds Discord's message size limit.
        """
        chunks = []
        while len(message) > DISCORD_MESSAGE_LIMIT:
            split_idx = message.rfind("\n", 0, DISCORD_MESSAGE_LIMIT)
            if split_idx == -1:
                split_idx = DISCORD_MESSAGE_LIMIT
            chunks.append(message[:split_idx])
            message = message[split_idx:].lstrip("\n")
        if message:
            chunks.append(message)

        for chunk in chunks:
            self._post_chunk(channel_id, chunk)

    def _post_chunk(self, channel_id, chunk):
        """
        Send a single message chunk via the REST API, off the reactor thread.
        """

        def _failed(failure):
            logger.error(
                "Failed to send message to Discord channel %s: %s", channel_id, failure.value
            )

        d = threads.deferToThread(
            api, f"channels/{channel_id}/messages", method="POST", json_data={"content": chunk}
        )
        d.addErrback(_failed)

    def leave(self, channel, *args, **kwargs):
        msg = (
            "Bots cannot leave individual Discord channels. Remove the bot from the server instead"
        )
        logger.warning("Cannot leave %s: %s", channel, msg)
        return msg

    def join(self, channel, *args, **kwargs):
        msg = (
            "Bots cannot join Discord channels or servers on their own. "
            "Use an OAuth2 invite link to add the bot to a server instead"
        )
        logger.warning("Cannot join %s: %s", channel, msg)
        return msg

    def get_channel_logger(self, channel):
        """
        Gets a channel logger, keeping track of previously requested ones.
        (see :ref:`builtin.channel_logging`)

        :param channel: A channel name
        :returns: a python logger suitable for channel logging
        """
        if channel not in self.channel_loggers:
            self.channel_loggers[channel] = log.get_channel_logger(channel)
        return self.channel_loggers[channel]

    def log_channel_message(self, channel, nick, message):
        """
        Logs a message by a user on a channel using a channel logger.
        If channel logging is not enabled, nothing happens.
        (see :ref:`builtin.channel_logging`)

        :param channel: A channel name
        :param nick: The nick of the user sending the message
        :param message: The message
        """
        if not settings.CHANNEL_LOGGING:
            return
        chan_logger = self.get_channel_logger(channel)
        chan_logger.info(message, extra={"nick": nick})

    def _get_channel_name(self, channel_id):
        """
        Get the channel name for a channel ID.
        """
        return self._channel_names.get(channel_id, "")

    def _get_channel_id(self, name):
        """
        Get the channel ID for a channel name.
        """
        name = name.lstrip("#")

        for chan_id, chan_name in self._channel_names.items():
            if chan_name == name:
                return chan_id

        return None

    def _get_user_name(self, user_id):
        """
        Get the username for a user ID.
        """
        return self._user_names.get(user_id, "")

    def _get_user_id(self, name):
        """
        Get the ID for a user, searching by name.
        """
        name = name.lstrip("@")

        for user_id, user_name in self._user_names.items():
            if user_name == name:
                return user_id

        return None

    def _parse_incoming_message(self, message, mentions=None):
        """
        Discord uses "<@USERID>" or "<@!USERID>" to mention a user, and
        "<#CHANNELID>" to mention a channel. Translate these into human-readable
        forms of "@user" and "#channel" respectively, consulting the message's own
        ``mentions`` payload before falling back to the internally cached names.
        """
        mention_names = {u["id"]: u.get("username", "") for u in (mentions or [])}

        def _sub_user(match):
            user_id = match.group(1)
            name = mention_names.get(user_id) or self._get_user_name(user_id)
            return f"@{name}" if name else match.group(0)

        message = re.sub(r"<@!?(\d+)>", _sub_user, message)

        def _sub_channel(match):
            channel_id = match.group(1)
            name = self._get_channel_name(channel_id)
            return f"#{name}" if name else match.group(0)

        message = re.sub(r"<#(\d+)>", _sub_channel, message)

        return html.unescape(message)

    def _sanitize(self, message):
        """
        Sanitize an outgoing message before sending to Discord. In particular,
        this escapes "@everyone" and "@here" mentions using a zero-width space so
        that helga plugins can't be tricked (or accidentally used) into mass-
        pinging a channel.
        """
        message = re.sub(r"@everyone", "@\u200beveryone", message)
        message = re.sub(r"@here", "@\u200bhere", message)
        return message


class DiscordError(RuntimeError):
    """
    Raise this when the Discord REST API returns an error.
    """

    def __init__(self, api, status_code=None, error=None, *args):
        self.api = api
        self.status_code = status_code
        self.error = error

        message = f"{error} in {api}" if error else f"Error in {api}"
        if status_code:
            message = f"HTTP {status_code}: {message}"

        self.message = message
        super().__init__(message, *args)
