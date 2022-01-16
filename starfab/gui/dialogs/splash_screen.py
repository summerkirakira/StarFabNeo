
from starfab.gui import qtc, qtw, qtg
from starfab.resources import RES_PATH


class StarFabSplashScreen(qtw.QSplashScreen):
    def __init__(self, starfab):
        self.starfab = starfab
        pixmap = qtg.QPixmap(str(RES_PATH / 'splash2.png'))
        super().__init__(starfab, pixmap, qtc.Qt.SplashScreen)
        self.progress_bar = qtw.QProgressBar(self)
        self.progress_bar.setGeometry(0, pixmap.height() - 40, pixmap.width(), 40)

    def mousePressEvent(self, event) -> None:
        return None  # override close on click

    def update_status_bar(self, progress_tasks):
        min = 0
        max = 0
        value = 0
        msgs = []
        for task in progress_tasks.values():
            if task['msg']:
                msgs.append(task['msg'])
            value += task['value']
            min += task['min']
            max += task['max']

        msg = ', '.join(msgs).strip()
        self.progress_bar.setFormat(f'{msg} - %v / %m - %p%' if msg else '%v / %m - %p%')
        self.progress_bar.setRange(min, max)
        self.progress_bar.setValue(value)
        if self.progress_bar.isHidden():
            self.progress_bar.show()
