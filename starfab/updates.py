import requests
import webbrowser
from packaging import version
from datetime import datetime, timedelta

from scdatatools.utils import parse_bool

from starfab import __version__
from starfab.gui import qtc, qtw, qtg
from starfab.settings import settings
from starfab.log import getLogger


logger = getLogger(__name__)
PROJECT_ID = 22934039
API_URL = f'https://gitlab.com/api/v4/projects/{PROJECT_ID}/releases'


def check_for_update(url=API_URL) -> (bool, str, str):
    """ Checks if there is a newer version available for download from the given gitlab project url.

    :returns: `bool` whether there is a newer version, `str` of the latest version and a `str` of the download url
        for the latest version
    """
    current_version = version.parse(__version__)
    try:
        r = requests.get(url)
        r.raise_for_status()
        latest = r.json()[0]
        latest_version = version.parse(latest['tag_name'])

        return latest_version > current_version, latest_version, latest.get('_links', {}).get('self', ''), latest
    except (requests.HTTPError, IndexError):
        pass
    return False, current_version, '', {}


class UpdateAvailableDialog(qtw.QDialog):
    def __init__(self, version, version_link, release, parent=None):
        super().__init__(parent)
        self.setWindowTitle('Update Available')

        self.version = version
        self.version_link = version_link
        self.release = release
        self.setMinimumWidth(400)

        layout = qtw.QVBoxLayout()

        label = qtw.QLabel(f'StarFab {version} is now available for download!')
        label.setStyleSheet("font-weight: bold; font-size: 20px")
        layout.addWidget(label)

        description = qtw.QTextBrowser()
        description.setOpenExternalLinks(True)
        description.setHtml(f"<pre>{release.get('description', '')}</pre>")
        layout.addWidget(description)

        btn_widget = qtw.QWidget()
        btn_layout = qtw.QHBoxLayout()
        btn_layout.setContentsMargins(0, 0, 0, 0)

        skip_version_btn = qtw.QPushButton(f'Skip this version')
        skip_version_btn.clicked.connect(self.skip)
        btn_layout.addWidget(skip_version_btn)

        btn_layout.addItem(qtw.QSpacerItem(40, 20, qtw.QSizePolicy.Expanding, qtw.QSizePolicy.Minimum))

        remind_btn = qtw.QPushButton(f'Remind me later')
        remind_btn.clicked.connect(self.remind)
        btn_layout.addWidget(remind_btn)

        download_btn = qtw.QPushButton(f'Download')
        download_btn.clicked.connect(self.download)
        btn_layout.addWidget(download_btn)
        btn_widget.setLayout(btn_layout)

        layout.addWidget(btn_widget)
        self.setLayout(layout)

    def remind(self):
        later = f'{self.version}!{(datetime.now() + timedelta(days=1)).timestamp()}'
        settings.setValue('updateRemindLater', later)
        self.close()

    def skip(self):
        settings.setValue('ignoreUpdate', str(self.version))
        self.close()

    def download(self):
        webbrowser.open(self.version_link)
        self.close()


def check_and_notify():
    if not parse_bool(settings.value('checkForUpdates', 'true')):
        return

    update_available, latest_version, update_link, release = check_for_update()

    update_remind_later = settings.value('updateRemindLater', '')
    should_remind = True

    if (iv := settings.value('ignoreUpdate')) and version.parse(iv) == latest_version:
        should_remind = False
    if should_remind and update_remind_later:
        try:
            remind_later_version, remind_time = update_remind_later.split('!')
            remind_later_version = version.parse(remind_later_version)
            remind_time = datetime.fromtimestamp(float(remind_time))
            if remind_later_version < latest_version or remind_time < datetime.now():
                settings.value('updateRemindLater', '')
            else:
                should_remind = False
        except Exception:
            pass

    if update_available:
        logger.debug(f'New version found {latest_version}: {update_link}')

    if update_available and should_remind:
        UpdateAvailableDialog(latest_version, update_link, release).exec_()
