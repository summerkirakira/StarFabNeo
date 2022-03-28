import os
import sys
import logging
import threading
import logging.config

from qtpy.QtCore import QThread

LOG_OVERRIDE = os.environ.get("STARFAB_LOG_OVERRIDE", None)
DEFAULT_LOG_LEVEL = "INFO"
MAX_LOG_FILE_SIZE = 20 * 1024 * 1024  # 20m
MAX_LOG_FILES = 2


class LowPassFilter:
    def __init__(self, level):
        self.level = level

    def filter(self, log):
        return log.levelno <= self.level


class HighPassFilter(LowPassFilter):
    def filter(self, log):
        return log.levelno >= self.level


class ThreadLogFormatter(logging.Formatter):
    thread_fmt = logging.Formatter(
        "%(asctime)s [%(levelname)s] [%(qThreadName)s] %(name)s: %(message)s"
    )
    default_fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")

    def format(self, record):
        if getattr(record, "qThreadName", ""):
            return self.thread_fmt.format(record)
        return self.default_fmt.format(record)


class ThreadLogger:
    def __init__(self, name):
        self.logger = logging.getLogger(name)

    def log(self, level, msg, extra=None, *args, **kwargs):
        if extra is None:
            extra = {}
        extra["qThreadName"] = QThread.currentThread().objectName()
        if not extra["qThreadName"]:
            extra["qThreadName"] = threading.get_ident()
        else:
            extra["qThreadName"] += f"-{threading.get_ident()}"
        self.logger.log(level, msg, extra=extra, *args, **kwargs)

    def debug(self, msg, *args, **kwargs):
        self.log(logging.DEBUG, msg, *args, **kwargs)

    def info(self, msg, *args, **kwargs):
        self.log(logging.INFO, msg, *args, **kwargs)

    def warning(self, msg, *args, **kwargs):
        self.log(logging.WARNING, msg, *args, **kwargs)

    def error(self, msg, *args, **kwargs):
        self.log(logging.ERROR, msg, *args, **kwargs)

    def critical(self, msg, *args, **kwargs):
        self.log(logging.CRITICAL, msg, *args, **kwargs)

    def fatal(self, msg, *args, **kwargs):
        self.log(logging.FATAL, msg, *args, **kwargs)

    def exception(self, msg, *args, **kwargs):
        kwargs.setdefault("exc_info", 1)
        self.log(logging.ERROR, msg, *args, **kwargs)


def getLogger(name):
    return ThreadLogger(name)


logger = getLogger("starfab")


DEFAULT_LOGGING_CONFIG = {
    "version": 1,
    "disable_existing_loggers": True,
    "filters": {
        "infofilter": {"()": LowPassFilter, "level": logging.INFO},
        "warnfilter": {"()": HighPassFilter, "level": logging.WARNING},
    },
    "formatters": {
        "standard": {"()": ThreadLogFormatter},
    },
    "handlers": {
        "console": {
            "level": LOG_OVERRIDE or DEFAULT_LOG_LEVEL,
            "class": "logging.StreamHandler",
            "formatter": "standard",
            "stream": "ext://sys.stdout",
            "filters": ["infofilter"],
        },
        "console_err": {
            "level": "WARN",
            "class": "logging.StreamHandler",
            "formatter": "standard",
            "stream": "ext://sys.stderr",
            "filters": ["warnfilter"],
        },
        "logfile": {
            "level": LOG_OVERRIDE or DEFAULT_LOG_LEVEL,
            "class": "logging.handlers.RotatingFileHandler",
            "formatter": "standard",
            "filename": "starfab.log",
            "mode": "a",
            "maxBytes": MAX_LOG_FILE_SIZE,
            "backupCount": MAX_LOG_FILES,
        },
    },
    "loggers": {
        "": {  # root logger
            "handlers": ["console_err", "logfile"],
            "level": "INFO",
            "propagate": False,
        },
        "sentry": {
            "handlers": ["console_err", "logfile"],
            "level": LOG_OVERRIDE
                     or os.environ.get("STARFAB_LOG", "")
                     or DEFAULT_LOG_LEVEL,
            "propagate": False,
        },
        "starfab": {
            "handlers": ["console_err", "logfile"],
            "level": LOG_OVERRIDE
            or os.environ.get("STARFAB_LOG", "")
            or DEFAULT_LOG_LEVEL,
            "propagate": False,
        },
        "scdatatools": {
            "handlers": ["console_err", "logfile"],
            "level": LOG_OVERRIDE
            or os.environ.get("SCDT_LOG", "")
            or DEFAULT_LOG_LEVEL,
            "propagate": False,
        },
    },
}


def setup_logging():
    if sys.executable.lower().endswith("pythonw.exe") or sys.executable.lower().endswith("starfab.exe"):
        # on windows - if we're running as a "window" (without a console) redirect stdout/stderr to files
        sys.stdout = open("starfab.out", "w")
        sys.stderr = open("starfab.err", "w")
    else:
        for logger in DEFAULT_LOGGING_CONFIG['loggers']:
            DEFAULT_LOGGING_CONFIG['loggers'][logger]['handlers'].extend(['console', 'console_err'])

    logging.config.dictConfig(DEFAULT_LOGGING_CONFIG)
    # logging.debug('test')
    # logging.info('test')
    # logging.warning('test')
    # logging.critical('test')
    # logging.error('test')
    # try:
    #     d = 1/0
    # except ZeroDivisionError:
    #     logging.exception(f'test exception')


