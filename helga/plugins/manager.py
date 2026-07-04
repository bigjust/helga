import random

import smokesignal

from helga import log
from helga.db import (
    add_auto_enabled_channel,
    get_auto_enabled_plugins,
    get_connection,
    remove_auto_enabled_channel,
)
from helga.plugins import ACKS, command, registry

logger = log.getLogger(__name__)


@smokesignal.on("signon")
def auto_enable_plugins(*args):
    if get_connection() is None:  # pragma: no cover
        logger.warning("Cannot auto enable plugins. No database connection")
        return

    def pred(rec):
        return rec["plugin"] in registry.all_plugins

    for rec in filter(pred, get_auto_enabled_plugins()):
        for channel in rec["channels"]:
            logger.info("Auto-enabling plugin %s on channel %s", rec["plugin"], channel)
            registry.enable(channel, rec["plugin"])


def list_plugins(client, channel):
    enabled = set(registry.enabled_plugins[channel])
    available = registry.all_plugins - enabled

    return [
        "Plugins enabled on this channel: {}".format(", ".join(sorted(enabled))),
        "Available plugins: {}".format(", ".join(sorted(available))),
    ]


def _filter_valid(channel, *plugins):
    return [p for p in plugins if p in registry.all_plugins]


def enable_plugins(client, channel, *plugins):
    valid_plugins = _filter_valid(channel, *plugins)
    if not valid_plugins:
        return "Sorry, but I don't know about these plugins: {}".format(", ".join(plugins))

    registry.enable(channel, *valid_plugins)

    for p in valid_plugins:
        add_auto_enabled_channel(p, channel)

    return random.choice(ACKS)


def disable_plugins(client, channel, *plugins):
    valid_plugins = _filter_valid(channel, *plugins)
    if not valid_plugins:
        return "Sorry, but I don't know about these plugins: {}".format(", ".join(plugins))

    registry.disable(channel, *valid_plugins)

    for p in valid_plugins:
        remove_auto_enabled_channel(p, channel)

    return random.choice(ACKS)


@command(
    "plugins", help="Plugin management. Usage: helga plugins (list|(enable|disable) (<name> ...))"
)
def manager(client, channel, nick, message, cmd, args):
    """
    Manages listing plugins, or enabling and disabling them
    """
    subcmd = "list" if len(args) < 1 else args[0]

    if subcmd == "list":
        return list_plugins(client, channel)

    if subcmd == "enable":
        return enable_plugins(client, channel, *args[1:])

    if subcmd == "disable":
        return disable_plugins(client, channel, *args[1:])
