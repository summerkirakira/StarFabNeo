import json
import socket
import logging
from contextlib import closing

from .conf import BLENDERLINK_CONFIG


def find_free_port():
    with closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as s:
        s.bind(('', 0))
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        return s.getsockname()[1]


def parse_auth_token(token):
    if isinstance(token, bytes):
        token = token.decode('utf-8')
    if ':' in token:
        return token.split(':', maxsplit=1)
    return '', ''


def get_blenderlink_config_port():
    if BLENDERLINK_CONFIG.is_file():
        try:
            with BLENDERLINK_CONFIG.open('r') as config:
                return json.load(config).get('port')
        except json.decoder.JSONDecodeError:
            pass
    return None