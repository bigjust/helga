"""
Stdin/stdout chat backend for local CLI interaction with helga.
"""

import sys

from twisted.internet import reactor, stdio
from twisted.protocols.basic import LineOnlyReceiver

from helga import settings
from helga.comm.base import BaseClient
from helga.plugins import registry


class Factory:
    """
    Factory for the CLI backend. Instantiates a single :class:`Client` and wires it
    to Twisted's stdio transport.
    """

    def __init__(self):
        self.client = Client()

    def run(self):
        stdio.StandardIO(self.client)


class Client(LineOnlyReceiver, BaseClient):
    """
    A chat client that reads messages from stdin and writes responses to stdout.
    Messages are processed as if they were sent to the public channel ``#cli``.
    """

    delimiter = b"\n"
    nickname = settings.NICK

    def __init__(self):
        BaseClient.__init__(self)
        self.channels.add("#cli")

    def connectionMade(self):
        super().connectionMade()
        self._print(f"{settings.NICK} is ready on #cli. Type /quit to exit.")

    def lineReceived(self, line):
        try:
            message = line.decode("utf-8").strip()
        except UnicodeDecodeError:
            return

        if not message:
            return

        if message == "/quit":
            self.transport.loseConnection()
            return

        channel = "#cli"
        nick = "me"

        channel, nick, message = registry.preprocess(self, channel, nick, message)
        responses = registry.process(self, channel, nick, message)

        for response in responses:
            self.msg(channel, response)

        self.last_message[channel][nick] = message

    def msg(self, channel, message):
        for line in message.splitlines():
            self._print(f"<{settings.NICK}> {line}")

    def me(self, channel, message):
        self._print(f"* {settings.NICK} {message}")

    def connectionLost(self, reason):
        if reactor.running:
            reactor.stop()

    def _print(self, text):
        sys.stdout.write(text + "\n")
        sys.stdout.flush()
