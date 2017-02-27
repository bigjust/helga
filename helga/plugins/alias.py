import smokesignal

from helga import log
from helga.db import db
from helga.plugins import command

logger = log.getLogger(__name__)

def get_nick_map():

    nick_map_doc = db.alias.find_one()
    nick_map = nick_map_doc['nick_map']
    if not nick_map:
        nick_map = []
        logger.info('nick_map now found, creating...')
        update_nick_map(nick_map)

    return nick_map

def update_nick_map(nick_map):
    result = db.alias.replace_one({}, {'nick_map': nick_map}, True)
    logger.info('result.modified: %s', result.modified_count)

def find_nick(nick):
    """
    Returns list where nick is found in nick_map, else returns []
    """

    matched_nick_list = []
    for nick_list in get_nick_map():
        if nick in nick_list:
            matched_nick_list = nick_list
            break

    return matched_nick_list

@command('alias', help='Shows the nick map, should allow modification')
def alias(client, channel, nick, message, cmd, args):
    """

    Show the nick map.

    Should allow 1. adds, removes, joins, splits

    """

    logger.info('cmd: %s', cmd)
    logger.info('args: %s', args)

    for nick_list in get_nick_map():
        client.msg(channel, u'{}'.format(nick_list))

@smokesignal.on('names_reply')
def add_names(client, nicks):

    nick_map = get_nick_map()

    for nick in nicks:
        found = find_nick(nick)
        if not found:
            nick_map.append([nick])
            update_nick_map(nick_map)

@smokesignal.on('user_rename')
def user_rename(client, oldname, newname):

    nick_map = get_nick_map()
    nick_list = find_nick(oldname)

    if not nick_list:
        nick_map.append([oldname, newname])
    else:
        for nlist in nick_map:
            if nlist == nick_list:
                if newname not in nlist:
                    nlist.append(newname)
                break

    update_nick_map(nick_map)
