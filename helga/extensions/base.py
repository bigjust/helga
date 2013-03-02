import random
import re

from docopt import docopt, DocoptExit


class HelgaExtension(object):
    """
    Defines a dispatchable API for extensions and extra functionality
    """
    acks = (
        'roger',
        '10-4',
        'no problem %(nick)s',
        'will do',
        'you got it %(nick)s',
        'anything you say %(nick)s',
        'sure thing',
        'ok',
        'right-o',
    )

    add_acks = acks + (
        '%(nick)s, added',
        'consider it done',
    )

    delete_acks = acks + (
        '%(nick)s, deleted',
        'nuking from orbit',
        'consider it done',
        "annnnd it's gone",
    )

    def __init__(self, bot):
        self.bot = bot

    def random_ack(self):
        return random.choice(self.acks)

    def on(self, event, *args, **kwargs):
        """
        Event delegation receiver

        perhaps should be named HelgaEventDelegationReceiverFactory?!?
        """
        pass

    def preprocess(self, message):
        """
        Any filter-type action that should happen before dispatch is called
        """
        pass

    def process(self, message):
        """
        Process a message object and attach any response to it
        """
        pass


class CommandExtension(HelgaExtension):
    """
    Command type extension. Implementers should supply a class attribute:

    usage: docopt supported string. this should _always_ start with [BOTNICK]
           unless the behavior of `should_handle_message` is altered
    """

    # This should ONLY be the argument string
    usage = '[BOTNICK] [COMMAND] [INPUT ...]'

    def parse_command(self, message):
        argv = message.message.strip().split()

        # make sure usage is right - this is a docopt complainy thing. maybe i'll fix it.
        if not self.usage.lower().startswith('usage: irc '):
            self.usage = 'Usage: irc %s' % self.usage

        try:
            return docopt(self.usage, argv=argv, help=False)
        except DocoptExit:
            return None

    def should_handle_message(self, opts, message):
        botnick = opts.get('BOTNICK', '')

        if not opts:
            return False
        elif botnick and botnick == self.bot.nick:
            return True
        elif not message.is_public and not botnick:
            return True

        return False

    def handle_message(self, opts, message):
        """
        Handle the message. This should set message.response to None if no response
        is required, a string for a single line response, or a list of
        strings for a multiline response.

        Side effect: if you specify [INPUT ...] in `usage`, it will be returned
        as a list of strings, not one single string. Sorry...
        """
        pass

    def process(self, message):
        opts = self.parse_command(message)

        if opts and self.should_handle_message(opts, message):
            self.handle_message(opts, message)


class ContextualExtension(HelgaExtension):
    """
    Contextualizes messages by responding to any match in message content.
    Implementers should provide the following class attributes:

    context: regular expression string to test against incoming messages
    allow_many: boolean. True returns all transformed matches. False returns the first
    response_fmt: response format string. Should at minimum contain format '%(response)s'.
                  optionally can contain %(nick)s to refer to the user sending the message

    Implementers should also provide a mechanism to transform a match into a readable
    string by overriding `transform_match`.
    """
    context = None
    allow_many = False
    response_fmt = '%(nick)s might be talking about: %(response)s'

    def transform_match(self, match):
        """
        Converts a single match of re.findall() using the context against the
        incoming message
        """
        return match

    def contextualize(self, message):
        found = []

        for match in re.findall(self.context, message.message, re.I):
            found.append(self.transform_match(match))

        # filter Nones
        found = filter(lambda x: x is not None, found)

        if found:
            found = found if self.allow_many else [found[0]]

            message.response = self.response_fmt % {
                'nick': '%(nick)s',  # Yes, this is annoying, but whatever
                'response': ', '.join(found)
            }

    def process(self, message):
        if self.context:
            self.contextualize(message)
