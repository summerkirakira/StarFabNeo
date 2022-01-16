from pathlib import Path

LINK_SECRET_LEN = 32
LINK_TOKEN_LEN = 5 + 1 + (LINK_SECRET_LEN * 2)  # procid + ':' + secret
BLENDERLINK_CONFIG = Path("~/.starfab/blenderlink.json").expanduser()