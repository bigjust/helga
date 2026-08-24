helga
=====

.. image:: https://github.com/bigjust/helga/workflows/CI/badge.svg
    :target: https://github.com/bigjust/helga/actions

.. image:: https://codecov.io/gh/bigjust/helga/branch/master/graph/badge.svg
    :target: https://codecov.io/gh/bigjust/helga

.. image:: https://img.shields.io/pypi/v/helga.svg
    :target: https://pypi.python.org/pypi/helga

.. image:: https://img.shields.io/pypi/pyversions/helga.svg
    :target: https://pypi.python.org/pypi/helga



About
-----
Helga is a full-featured chat bot for Python 3.8+ using `Twisted`_. Helga originally started
as a python fork of a perl-based IRC bot `olga`_, but has grown considerably since then. Early
versions limited support to IRC, but now include other services like XMPP, HipChat, Slack, and Discord.
Full documentation can be found at http://helga.readthedocs.org.

**Note:** Version 2.0.0+ requires Python 3.8 or higher. For Python 2.7 support, use version 1.x.


Supported Backends
------------------

Helga supports IRC, XMPP, HipChat, Slack, Discord, and a local CLI backend out of the box. Note,
however, that helga originally started as an IRC bot, so much of the terminology will reflect that.
The current status of non-IRC support varies by backend. In the future, helga may have a much more
robust and pluggable backend system to allow connections to any number of chat services.

Local CLI Backend
^^^^^^^^^^^^^^^^^
For local development or testing without a chat server, helga can use a stdio-based CLI backend.
Messages are read from stdin and responses are written to stdout as if they were sent in the
``#cli`` channel.

To use it, set ``SERVER['TYPE']`` to ``'cli'`` in your settings file::

    SERVER = {
        'TYPE': 'cli',
    }

Run helga and type commands directly::

    $ helga --settings cli_settings.py
    helga is ready on #cli. Type /quit to exit.
    helga help
    ...
    /quit

Set ``LOG_LEVEL = 'WARNING'`` (or use ``LOG_FILE``) to keep log output from interleaving with the
chat output.

Discord Backend
^^^^^^^^^^^^^^^^
Helga can also connect to `Discord`_ as a bot application, talking directly to the Discord
gateway and REST APIs (no ``discord.py`` dependency required). To use it, create a bot
application and set ``SERVER['TYPE']`` to ``'discord'`` along with the bot token::

    SERVER = {
        'TYPE': 'discord',
        'API_KEY': 'your-bot-token',
    }

The bot's username is configured in the Discord developer portal and is detected
automatically, so there's no need to set :data:`~helga.settings.NICK` or
:data:`~helga.settings.COMMAND_PREFIX_BOTNICK`. See ``helga/comm/discord.py`` for details,
including the ``DISCORD_INTENTS`` setting for privileged gateway intents.

See ``settings_discord_example.py`` for a starting configuration, and
``docker-compose.discord.yml`` to run the bot in a container (with Postgres for
plugins that need persistence).


Contributing
------------
Contributions are **always** welcomed, whether they be in the form of bug fixes, enhancements,
or just bug reports. To report any issues, please create a ticket on `github`_. For code
changes, please note that any pull request will be denied a merge if the test suite fails.

See `CONTRIBUTING.md`_ for detailed contribution guidelines, including:

- Development setup with modern tools (Black, Ruff, Mypy)
- Pre-commit hooks for code quality
- Testing guidelines
- Code style standards
- Pull request process

If you are looking to get help with helga, join the #helgabot IRC channel on freenode.


Docker
------

A docker compose file is included with an IRC server (InspIRCd) and PostgreSQL.

Quick start:

::

    docker compose up -d
    # Connect to localhost:6667 and join #helga-dev

Developing a plugin
^^^^^^^^^^^^^^^^^^^

Clone your plugin repo alongside helga, then mount and auto-install it with a
compose overlay file.  For example, with ``helga-oral-history`` as a sibling:

Create ``docker-compose.dev.yml`` in the plugin repo:

.. code-block:: yaml

    services:
      helga:
        volumes:
          - ../helga-oral-history:/app/helga-oral-history:Z
        entrypoint: >
          sh -c "pip install -q -e /app/helga-oral-history
                 && exec /opt/venv/bin/helga --settings=/etc/helga_settings.py"

Run with the overlay:

::

    cd ~/code/helga
    docker compose -f docker-compose.yml -f ../helga-oral-history/docker-compose.dev.yml \
        up -d --force-recreate helga

Reload the plugin after editing, without restarting the container:

::

    !operator reload oral_history


Deployment
----------

IBM Cloud
~~~~~~~~~

Helga can be easily deployed to IBM Cloud using Cloud Foundry. A complete deployment guide,
configuration files, and automated deployment script are included:

- **Quick Start**: Run ``./deploy-ibmcloud.sh`` for an interactive deployment
- **Manual Deployment**: See ``IBM_CLOUD_DEPLOYMENT.md`` for detailed instructions
- **Configuration**: Edit ``ibmcloud_settings.py`` or use environment variables

The deployment includes:

- Cloud Foundry manifest (``manifest.yml``)
- IBM Cloud-specific settings (``ibmcloud_settings.py``)
- MongoDB service integration
- Environment-based configuration

For complete instructions, see `IBM_CLOUD_DEPLOYMENT.md`_.

License
-------
Copyright (c) 2014 Shaun Duncan

Helga is open source software, dual licensed under the `MIT`_ and `GPL`_ licenses. Dual licensing
was chosen for this project so that plugin authors can create plugins under their choice
of license that is compatible with this project.

Modernization
-------------

Helga has been modernized with current Python best practices and tooling. See `MODERNIZATION.md`_
for details on:

- Modern Python packaging (pyproject.toml)
- GitHub Actions CI/CD
- Pre-commit hooks and linting (Ruff, Black, Mypy)
- Enhanced Docker configuration
- Automated dependency updates

.. _`Discord`: https://discord.com/
.. _`GPL`: https://github.com/bigjust/helga/blob/master/LICENSE-GPL
.. _`MIT`: https://github.com/bigjust/helga/blob/master/LICENSE-MIT
.. _`Twisted`: https://twistedmatrix.com/trac/
.. _`olga`: https://github.com/thepeopleseason/olga
.. _`github`: https://github.com/bigjust/helga/issues
.. _`IBM_CLOUD_DEPLOYMENT.md`: IBM_CLOUD_DEPLOYMENT.md
.. _`CONTRIBUTING.md`: CONTRIBUTING.md
.. _`MODERNIZATION.md`: MODERNIZATION.md
