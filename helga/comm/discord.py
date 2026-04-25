"""
Twisted protocol and communication implementations for Discord
"""

import json
import re

import smokesignal
import requests

from functools import partial

from twisted.internet import reactor, task
from autobahn.twisted.websocket import WebSocketClientFactory
from autobahn.twisted.websocket import WebSocketClientProtocol

from helga import settings, log
from helga.comm.base import BaseClient
from helga.plugins import registry


logger = log.getLogger(__name__)

DISCORD_API_BASE = 'https://discord.com/api/v10'
DISCORD_INTENTS_GUILDS = 1 << 0
DISCORD_INTENTS_GUILD_MESSAGES = 1 << 9
DISCORD_INTENTS_DIRECT_MESSAGES = 1 << 12
DISCORD_INTENTS_MESSAGE_CONTENT = 1 << 15
DISCORD_OP_DISPATCH = 0
DISCORD_OP_HEARTBEAT = 1
DISCORD_OP_IDENTIFY = 2
DISCORD_OP_HELLO = 10
DISCORD_OP_HEARTBEAT_ACK = 11


def _headers():
    return {
        'Authorization': 'Bot {0}'.format(settings.SERVER['API_KEY']),
        'Content-Type': 'application/json',
    }


def api(method, path, **data):
    url = DISCORD_API_BASE + path
    logger.debug('Discord API request: %s %s -> %s', method, path, data)

    response = requests.request(method, url, headers=_headers(), json=data or None)

    if response.status_code >= 400:
        raise DiscordError(method=method, path=path, error=response.text)

    if response.content:
        return response.json()

    return {}


class Factory(WebSocketClientFactory):
    """
    Handle Discord gateway discovery and websocket factory creation.
    """

    def __init__(self):
        logger.info('Initiating Discord gateway discovery')
        data = api('GET', '/gateway/bot')

        gateway_url = '{0}?v=10&encoding=json'.format(data['url'])
        self.protocol = partial(Client, data)

        logger.info('creating WebSocketClientFactory with %s', gateway_url)

        return WebSocketClientFactory.__init__(self, url=gateway_url)

    def clientConnectionLost(self, connector, reason):
        logger.info('Connection to server lost: %s', reason)

        if getattr(settings, 'AUTO_RECONNECT', True):
            delay = getattr(settings, 'AUTO_RECONNECT_DELAY', 5)
            reactor.callLater(delay, connector.connect)
        else:
            raise reason

    def clientConnectionFailed(self, connector, reason):
        logger.warning('Connection to server failed: %s', reason)

        if getattr(settings, 'AUTO_RECONNECT', True):
            delay = getattr(settings, 'AUTO_RECONNECT_DELAY', 5)
            reactor.callLater(delay, connector.connect)
        else:
            reactor.stop()


class Client(WebSocketClientProtocol, BaseClient):

    def __init__(self, gateway_data, *a, **kw):
        BaseClient.__init__(self)

        users = gateway_data.get('users') or []

        self.nickname = settings.NICK
        self.session_id = None
        self.sequence = None
        self.user_id = None
        self._heartbeat = None
        self._guild_channel_names = {}
        self._private_channels = {}
        self._user_names = {}
        self._bot = None

        self._cache_all_user_names(users)

        return WebSocketClientProtocol.__init__(self, *a, **kw)

    def onMessage(self, msg, binary):
        try:
            data = json.loads(msg)
        except ValueError as e:
            logger.error('Error parsing WebSocket message %s : %s', msg, e)
            return

        op = data.get('op')
        event_type = data.get('t')
        payload = data.get('d')
        self.sequence = data.get('s', self.sequence)

        if op == DISCORD_OP_HELLO:
            return self.discord_hello(payload)

        if op == DISCORD_OP_HEARTBEAT_ACK:
            return

        if op == DISCORD_OP_DISPATCH and event_type:
            method_name = 'discord_{0}'.format(event_type.lower())

            try:
                getattr(self, method_name)(payload)
            except AttributeError:
                logger.info('No implementation for %r', method_name)
            except Exception:
                logger.exception('Failed to handle method call to %s', method_name)
            return

        if op == DISCORD_OP_HEARTBEAT:
            return self._send_heartbeat()

    def onClose(self, was_clean, code, reason):
        self._stop_heartbeat()

    def discord_hello(self, data):
        interval = float(data['heartbeat_interval']) / 1000.0
        self._start_heartbeat(interval)
        self._identify()

    def discord_ready(self, data):
        user = data.get('user', {})
        self.nickname = user.get('username', self.nickname)
        self.user_id = user.get('id')
        self.session_id = data.get('session_id')
        self._bot = user

        settings.COMMAND_PREFIX_BOTNICK = '@?' + self.nickname

        for channel in data.get('private_channels', []):
            recipients = channel.get('recipients', [])
            self._cache_all_user_names(recipients)
            self._private_channels[channel['id']] = [u['id'] for u in recipients]

        for guild in data.get('guilds', []):
            if 'name' in guild:
                self.channels.add(guild['name'])

        smokesignal.emit('signon', self)

    def discord_channel_create(self, data):
        if data.get('type') == 1:
            recipients = data.get('recipients', [])
            self._cache_all_user_names(recipients)
            self._private_channels[data['id']] = [u['id'] for u in recipients]
        elif data.get('type') == 0 and 'name' in data:
            self._guild_channel_names[data['id']] = '#{0}'.format(data['name'])
            self.channels.add('#{0}'.format(data['name']))

    def discord_guild_create(self, data):
        for channel in data.get('channels', []):
            if channel.get('type') == 0:
                name = '#{0}'.format(channel['name'])
                self._guild_channel_names[channel['id']] = name
                self.channels.add(name)

    def discord_message_create(self, data):
        author = data.get('author', {})
        user = author.get('username', '')
        channel = self._get_channel_name(data.get('channel_id'))
        message = data.get('content', '')

        if author.get('id'):
            self._user_names[author['id']] = user

        if not user or not channel or author.get('id') == self.user_id or author.get('bot'):
            return

        message = self._parse_incoming_message(message)

        logger.debug('[<--] %s/%s - %s', channel, user, message)

        try:
            channel, user, message = registry.preprocess(self, channel, user, message)
        except (TypeError, ValueError):
            pass

        self.last_message[channel][user] = message

        responses = registry.process(self, channel, user, message)

        if responses:
            return self.msg(channel, u'\n'.join(responses))

    def msg(self, channel, message):
        message = self._sanitize(message)

        logger.debug('[-->] %s - %s', channel, message)

        channel_id = self._get_channel_id(channel)

        if not channel_id:
            logger.warning('Cannot send message, unknown channel %s', channel)
            return

        return api('POST', '/channels/{0}/messages'.format(channel_id), content=message)

    def me(self, channel, message):
        logger.debug('[-->] %s - /me %s', channel, message)
        return self.msg(channel, '_{0}_'.format(message))

    def join(self, channel, *args, **kwargs):
        msg = 'Discord channels cannot be joined by the gateway client'
        logger.warning('Cannot join %s: %s', channel, msg)
        return msg

    def leave(self, channel, *args, **kwargs):
        msg = 'Discord channels cannot be left by the gateway client'
        logger.warning('Cannot leave %s: %s', channel, msg)
        return msg

    def _identify(self):
        payload = {
            'op': DISCORD_OP_IDENTIFY,
            'd': {
                'token': settings.SERVER['API_KEY'],
                'intents': (
                    DISCORD_INTENTS_GUILDS |
                    DISCORD_INTENTS_GUILD_MESSAGES |
                    DISCORD_INTENTS_DIRECT_MESSAGES |
                    DISCORD_INTENTS_MESSAGE_CONTENT
                ),
                'properties': {
                    '$os': 'linux',
                    '$browser': 'helga',
                    '$device': 'helga',
                },
            },
        }
        self.sendMessage(json.dumps(payload))

    def _send_heartbeat(self):
        self.sendMessage(json.dumps({
            'op': DISCORD_OP_HEARTBEAT,
            'd': self.sequence,
        }))

    def _start_heartbeat(self, interval):
        self._stop_heartbeat()
        logger.info('Starting Discord heartbeat task')
        self._heartbeat = task.LoopingCall(self._send_heartbeat)
        self._heartbeat.start(interval, now=False)

    def _stop_heartbeat(self):
        if self._heartbeat is not None:
            logger.info('Stopping Discord heartbeat task')
            self._heartbeat.stop()
            self._heartbeat = None

    def _get_channel_name(self, channel_id):
        if channel_id in self._guild_channel_names:
            return self._guild_channel_names[channel_id]

        if channel_id in self._private_channels:
            recipient_ids = self._private_channels[channel_id]
            if recipient_ids:
                return self._get_user_name(recipient_ids[0])

        return ''

    def _get_channel_id(self, name):
        for channel_id, channel_name in self._guild_channel_names.items():
            if channel_name == name:
                return channel_id

        for channel_id, recipient_ids in self._private_channels.items():
            if recipient_ids and self._get_user_name(recipient_ids[0]) == name:
                return channel_id

        return None

    def _get_user_name(self, user_id):
        return self._user_names.get(user_id, '')

    def _cache_all_user_names(self, users):
        for user in users:
            if 'id' in user and 'username' in user:
                self._user_names[user['id']] = user['username']

    def _parse_incoming_message(self, message):
        user_regex = r'<@!?([0-9]+)>'
        for user_id in re.findall(user_regex, message):
            user = self._get_user_name(user_id)
            if user:
                message = re.sub(r'<@!?{0}>'.format(user_id), '@' + user, message)

        return message

    def _sanitize(self, message):
        return message[:2000]

    def discord_message_update(self, data):
        pass

    def discord_message_delete(self, data):
        pass

    def discord_guild_member_add(self, data):
        pass

    def discord_guild_member_remove(self, data):
        pass

    def discord_resumed(self, data):
        logger.info('Discord session resumed')


class DiscordError(RuntimeError):
    """
    Raise this when the Discord API returns an error.
    """
    def __init__(self, method, path, error, *args):
        self.method = method
        self.path = path
        self.error = error
        message = '%s in %s %s' % (error, method, path)
        self.message = message
        super(DiscordError, self).__init__(message, *args)

# Made with Bob
