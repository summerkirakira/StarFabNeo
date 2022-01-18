
from pathlib import Path
import qtvscodestyle as qtvsc

from starfab.log import getLogger

logger = getLogger(__name__)

RES_PATH = Path(__file__).parent.absolute()

themes = {}
for theme_file in (RES_PATH / "stylesheets").glob("*.json"):
    try:
        theme = qtvsc.loads_jsonc(theme_file.open().read())
        themes[theme.get('name', theme_file.stem)] = theme_file
    except Exception as e:
        logger.exception(f'Failed to load theme {theme_file}')
