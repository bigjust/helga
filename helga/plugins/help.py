from collections import defaultdict

from helga.plugins import command, registry


def format_help_string(name, *helps):
    return "[{}] {}".format(name, ". ".join(helps))


@command(
    "help",
    aliases=["halp"],
    help="Show the help string for any commands. Usage: helga help [<plugin>]",
)
def help(client, channel, nick, message, cmd, args):
    helps = defaultdict(list)
    default_help = "No help string for this plugin"

    for plugin_name in registry.enabled_plugins[channel]:
        try:
            plugin = registry.plugins[plugin_name]
        except KeyError:
            continue

        # A simple object
        if hasattr(plugin, "help"):
            helps[plugin_name].append(plugin.help or default_help)

        # A decorated function
        elif hasattr(plugin, "_plugins"):
            fn_helps = list(filter(bool, (getattr(x, "help", None) for x in plugin._plugins)))
            helps[plugin_name].extend(fn_helps or [default_help])

    try:
        plugin = args[0]
    except IndexError:
        pass
    else:
        if plugin not in registry.enabled_plugins[channel]:
            return f"Sorry {nick}, I don't know about that plugin"
        elif plugin not in helps:
            return f"Sorry {nick}, there's no help string for plugin '{plugin}'"

        # Single plugin, it's probably ok in the public channel
        return format_help_string(plugin, *helps[plugin])

    if channel != nick:
        client.me(channel, f"whispers to {nick}")

    retval = []
    # Send the message to the user
    for key, value in helps.items():
        retval.append(format_help_string(key, *value))

    retval.insert(0, f"{nick}, here are the plugins I know about")
    client.msg(nick, "\n".join(retval))
