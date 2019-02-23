import functools
import subprocess
import sys

from setuptools import setup, find_packages
from setuptools.command.test import test as TestCommand

import helga


class PyTest(TestCommand):
    def finalize_options(self):
        TestCommand.finalize_options(self)
        self.test_args = []
        self.test_suite = True

    def run_tests(self):
        return subprocess.call('tox')


setup(
    name=helga.__title__,
    version=helga.__version__,
    description=helga.__description__,
    classifiers=[
        'Development Status :: 5 - Production/Stable',
        'Topic :: Communications :: Chat :: Internet Relay Chat',
        'Framework :: Twisted',
        'License :: OSI Approved :: GNU General Public License v3 (GPLv3)',
        'License :: OSI Approved :: MIT License',
        'Operating System :: OS Independent',
        'Programming Language :: Python',
        'Programming Language :: Python :: 2',
        'Programming Language :: Python :: 2.7',
        'Topic :: Software Development :: Libraries :: Python Modules',
    ],
    keywords='helga bot irc xmpp jabber hipchat chat',
    author=helga.__author__,
    author_email='shaun.duncan@gmail.com',
    url='https://github.com/shaunduncan/helga',
    license=helga.__license__,
    packages=find_packages(),
    package_data={
        'helga': ['webhooks/logger/*.mustache'],
    },
    install_requires=[
        'cffi',
        'decorator==3.4.0',
        'pymongo',
        'pyOpenSSL',
        'pystache==0.5.4',
        'smokesignal==0.5',
        'Twisted',
    ],
    tests_require=[
        'freezegun',
        'mock',
        'pretend',
        'tox',
        'pytest',
    ],
    cmdclass={'test': PyTest},
    entry_points=dict(
        helga_plugins=[
            'help     = helga.plugins.help:help',
            'manager  = helga.plugins.manager:manager',
            'operator = helga.plugins.operator:operator',
            'ping     = helga.plugins.ping:ping',
            'version  = helga.plugins.version:version',
            'webhooks = helga.plugins.webhooks:WebhookPlugin',
        ],
        helga_webhooks=[
            'announcements = helga.webhooks.announcements:announce',
            'logger        = helga.webhooks.logger:logger'
        ],
        console_scripts=[
            'helga = helga.bin.helga:main',
        ],
    ),
)
