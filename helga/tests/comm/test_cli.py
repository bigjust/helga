from unittest.mock import Mock, patch

import pytest

from helga.comm import cli


@pytest.fixture
def client():
    return cli.Client()


class TestFactory:
    def test_run_starts_stdio(self):
        factory = cli.Factory()

        with patch("helga.comm.cli.stdio.StandardIO") as stdio:
            factory.run()
            stdio.assert_called_once_with(factory.client)


class TestClient:
    def test_client_uses_cli_channel(self, client):
        assert "#cli" in client.channels
        assert client.nickname == "helga"

    def test_connectionMade_prints_greeting(self, client, capsys):
        transport = Mock()
        client.makeConnection(transport)

        captured = capsys.readouterr()
        assert "helga is ready on #cli" in captured.out

    def test_lineReceived_processes_message(self, client):
        mock_registry = Mock()
        mock_registry.preprocess.return_value = ("#cli", "me", "ping")
        mock_registry.process.return_value = ["pong"]

        with patch.object(cli, "registry", mock_registry):
            with patch.object(client, "msg") as msg:
                client.lineReceived(b"ping")

                mock_registry.preprocess.assert_called_once_with(client, "#cli", "me", "ping")
                mock_registry.process.assert_called_once_with(client, "#cli", "me", "ping")
                msg.assert_called_once_with("#cli", "pong")

    def test_quit_disconnects(self, client):
        client.transport = Mock()
        client.lineReceived(b"/quit")
        client.transport.loseConnection.assert_called_once()

    def test_msg_prints_bot_nick(self, client, capsys):
        client.msg("#cli", "hello")
        captured = capsys.readouterr()
        assert captured.out == "<helga> hello\n"

    def test_msg_prints_multiline(self, client, capsys):
        client.msg("#cli", "line one\nline two")
        captured = capsys.readouterr()
        assert captured.out == "<helga> line one\n<helga> line two\n"

    def test_me_prints_action(self, client, capsys):
        client.me("#cli", "waves")
        captured = capsys.readouterr()
        assert captured.out == "* helga waves\n"
