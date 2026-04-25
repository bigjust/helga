# -*- coding: utf8 -*-

from mock import Mock, patch
from unittest import TestCase

from helga.comm import discord


class FactoryTestCase(TestCase):

    @patch('helga.comm.discord.api')
    def test_factory_uses_gateway_url(self, api):
        api.return_value = {'url': 'wss://gateway.discord.gg'}

        factory = discord.Factory()

        assert factory.url == 'wss://gateway.discord.gg?v=10&encoding=json'

    @patch('helga.comm.discord.settings')
    @patch('helga.comm.discord.reactor')
    def test_client_connection_lost_retries(self, reactor, settings):
        settings.AUTO_RECONNECT = True
        settings.AUTO_RECONNECT_DELAY = 1
        connector = Mock()
        factory = object.__new__(discord.Factory)
        factory.clientConnectionLost(connector, Exception)
        reactor.callLater.assert_called_with(1, connector.connect)

    @patch('helga.comm.discord.settings')
    def test_client_connection_lost_raises(self, settings):
        settings.AUTO_RECONNECT = False
        connector = Mock()
        factory = object.__new__(discord.Factory)
        self.assertRaises(Exception, factory.clientConnectionLost, connector, Exception)

    @patch('helga.comm.discord.settings')
    @patch('helga.comm.discord.reactor')
    def test_client_connection_failed(self, reactor, settings):
        settings.AUTO_RECONNECT = False
        factory = object.__new__(discord.Factory)
        factory.clientConnectionFailed(Mock(), reactor)
        assert reactor.stop.called

    @patch('helga.comm.discord.settings')
    @patch('helga.comm.discord.reactor')
    def test_client_connection_failed_retries(self, reactor, settings):
        settings.AUTO_RECONNECT = True
        settings.AUTO_RECONNECT_DELAY = 1
        connector = Mock()
        factory = object.__new__(discord.Factory)
        factory.clientConnectionFailed(connector, reactor)
        reactor.callLater.assert_called_with(1, connector.connect)


class ClientTestCase(TestCase):

    def setUp(self):
        with patch.object(discord.settings, 'NICK', 'helga'):
            self.client = discord.Client({
                'users': [
                    {'id': '1', 'username': 'alice'},
                    {'id': '2', 'username': 'bob'},
                ],
            })

    @patch('helga.comm.discord.smokesignal')
    def test_discord_ready_sets_identity(self, signal):
        with patch.object(discord.settings, 'COMMAND_PREFIX_BOTNICK', True):
            self.client.discord_ready({
                'user': {'id': '99', 'username': 'helga'},
                'session_id': 'abc',
                'private_channels': [],
                'guilds': [{'id': '10', 'name': 'guild-name'}],
            })

            assert self.client.nickname == 'helga'
            assert self.client.user_id == '99'
            assert self.client.session_id == 'abc'
            assert 'guild-name' in self.client.channels
            signal.emit.assert_called_with('signon', self.client)

    def test_discord_guild_create_caches_channel_names(self):
        self.client.discord_guild_create({
            'channels': [
                {'id': '100', 'type': 0, 'name': 'general'},
                {'id': '101', 'type': 2, 'name': 'voice'},
            ],
        })

        assert self.client._guild_channel_names['100'] == '#general'
        assert '#general' in self.client.channels
        assert '101' not in self.client._guild_channel_names

    def test_parse_incoming_message_simple(self):
        result = self.client._parse_incoming_message('<@1> Hi')
        assert '@alice Hi' == result

    def test_parse_incoming_message_nickname_mention(self):
        result = self.client._parse_incoming_message('<@!2> Hi')
        assert '@bob Hi' == result

    def test_get_channel_id_for_dm(self):
        self.client._private_channels = {'200': ['1']}
        assert self.client._get_channel_id('alice') == '200'

    @patch('helga.comm.discord.api')
    def test_msg_posts_to_channel(self, api):
        self.client._guild_channel_names = {'100': '#general'}
        self.client.msg('#general', 'hello')

        api.assert_called_with('POST', '/channels/100/messages', content='hello')

    @patch('helga.comm.discord.registry')
    def test_discord_message_create_sends_response(self, registry):
        registry.process.return_value = ['line1', 'line2']
        self.client.user_id = '99'
        self.client._guild_channel_names = {'100': '#general'}
        self.client.msg = Mock()

        self.client.discord_message_create({
            'channel_id': '100',
            'content': 'ping',
            'author': {'id': '1', 'username': 'alice'},
        })

        registry.process.assert_called_with(self.client, '#general', 'alice', 'ping')
        self.client.msg.assert_called_with('#general', 'line1\nline2')

    @patch('helga.comm.discord.registry')
    def test_discord_message_create_ignores_self(self, registry):
        self.client.user_id = '1'
        self.client._guild_channel_names = {'100': '#general'}

        self.client.discord_message_create({
            'channel_id': '100',
            'content': 'ping',
            'author': {'id': '1', 'username': 'alice'},
        })

        assert not registry.process.called

# Made with Bob
