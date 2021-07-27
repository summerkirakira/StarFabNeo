import os
import logging
from logging.handlers import RotatingFileHandler


DEFAULT_LOG_LEVEL = 'DEBUG'
MAX_LOG_FILE_SIZE = 20*1024*1024  # 20m
MAX_LOG_FILES = 2
LOG_FMT = '%(asctime)s [%(levelname)s] %(name)s: %(message)s'

logger = logging.getLogger('scdv')


def setup_logging():
    scdv_handler = RotatingFileHandler('scdv.log', mode='a', maxBytes=MAX_LOG_FILE_SIZE,
                                       backupCount=MAX_LOG_FILES, delay=False)
    log_level = logging.getLevelName(os.environ.get('SCDV_LOGLEVEL', DEFAULT_LOG_LEVEL))
    logging.basicConfig(format=LOG_FMT, datefmt='%H:%M:%S', level=log_level, handlers=[scdv_handler])
