import os
import random
import sys

import smokesignal
from twisted.internet import reactor

from helga import log
from helga.db import add_autojoin, get_autojoin_channels, get_connection, remove_autojoin
from helga.plugins import command, random_ack, registry

logger = log.getLogger(__name__)

nopes = [
    "You're not the boss of me",
    "Whatever I do what want",
    "You can't tell me what to do",
    "{nick}, this incident has been reported",
    "NO. You are now on notice {nick}",
]


@smokesignal.on("signon")
def join_autojoined_channels(client):
    if get_connection() is None:  # pragma: no cover
        logger.warning("Cannot autojoin channels. No database connection")
        return

    for channel in get_autojoin_channels():
        try:
            client.join(channel)
        except Exception:  # pragma: no cover
            logger.exception("Could not autojoin %s", channel)


@smokesignal.on("join")
def list_operators_on_join(client, channel):
    if client.operators:
        client.msg(channel, f"Operators: {', '.join(sorted(client.operators))}")


def do_add_autojoin(channel):
    logger.info("Adding autojoin channel %s", channel)

    if add_autojoin(channel):
        return random_ack()
    return "I'm already doing that"


def do_remove_autojoin(channel):
    logger.info("Removing autojoin %s", channel)
    remove_autojoin(channel)
    return random_ack()


def reload_plugin(plugin):
    """
    Hooks into the registry and reloads a plugin without restarting
    """
    if registry.reload(plugin):
        return f"Successfully reloaded plugin '{plugin}'"
    else:
        return f"Failed to reload plugin '{plugin}'"


@command(
    "operator",
    aliases=["oper", "op"],
    help="Admin like control over helga. Must be an operator to use. "
    "Usage: helga (operator|oper|op) (reload <plugin>|restart|quit|"
    "(join|leave|autojoin (add|remove)) <channel>)",
)
def operator(client, channel, nick, message, cmd, args):
    """
    Admin like control over helga. Can join/leave or add/remove autojoin channels. User asking
    for this command must have his or her nick listed in OPERATORS list in helga settings.
    """
    if nick not in client.operators:
        return random.choice(nopes).format(nick=nick)

    if not args:
        return (
            "Usage: helga (operator|oper|op) (reload <plugin>|restart|quit|"
            "(join|leave|autojoin (add|remove)) <channel>)"
        )

    subcmd = args[0]

    if subcmd in ("join", "leave"):
        channel = args[1]
        if channel.startswith("#"):
            return getattr(client, subcmd)(channel)

    elif subcmd == "autojoin":
        op, channel = args[1], args[2]
        if op == "add":
            return do_add_autojoin(channel)
        elif op == "remove":
            return do_remove_autojoin(channel)

    elif subcmd == "nsa":
        # Never document this
        return client.msg(args[1], " ".join(args[2:]))

    # Reload a plugin without restarting
    elif subcmd == "reload":
        if len(args) < 2:
            return "Usage: helga operator reload <plugin>"
        return reload_plugin(args[1])

    elif subcmd == "restart":
        # ponytail: execvp searches PATH if argv[0] has no slash; works when
        # helga is invoked via console_script (just 'helga') or an absolute path
        reactor.callLater(1, os.execvp, sys.argv[0], sys.argv)
        return "Restarting..."

    elif subcmd == "quit":
        reactor.callLater(1, reactor.stop)
        return "Shutting down..."
