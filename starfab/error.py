import sentry_sdk
import tkinter as tk
from tkinter.messagebox import Message

from scdatatools.utils import parse_bool

from .settings import settings


def show_error_dialog(title, message):
    root = tk.Tk()
    root.eval(f'tk::PlaceWindow . center')
    root.withdraw()
    root.lift()
    res = Message(
        master=root, type="yesno", icon="error",
        title=title, message=message
    ).show()
    root.destroy()
    return res == 'yes'


def sentry_error_handler(event, hint):
    if parse_bool(settings.value('enableErrorReporting', True)):
        if 'log_record' in hint:
            msg = hint['log_record']['message']
        else:
            msg = str(hint['exc_info'][1])
        should_send = show_error_dialog(
            "StarFab Exception",
            f"An exception has occurred in StarFab, would you like to submit an error report?\n\n{msg}"
        )
        if should_send:
            return event
    return None
