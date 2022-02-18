from PyQt5.QtWidgets import QWidget, QRadioButton
from PyQt5.QtCore import pyqtSignal, QObject

class RadioBtnList(QObject):
    btn_toggled = pyqtSignal(str)
    def __init__(self, **names_and_btns):
        super(RadioBtnList, self).__init__()
        self._btns = []
        self._names = []
        self._current_active = None

        for name, btn in names_and_btns.items():
            self._btns.append(btn)
            self._names.append(name)
            btn.toggled.connect(self.activate_btn)

    def activate_btn(self, val):
        sender = self.sender()
        sender_idx = self._btns.index(sender)
        btn_name = self._names[sender_idx]
        if self._current_active is None:
            self._current_active = sender
            self.btn_toggled.emit(btn_name)
        elif self._current_active != sender:
            self._current_active.setChecked(False)
            self._current_active = sender
            self.btn_toggled.emit(btn_name)

    def setChecked(self, btn_name):
        btn_idx = self._names.index(btn_name)
        activate_btn = self._btns[btn_idx]
        activate_btn.setChecked(True)

    def get_active_name(self):
        btn_idx = self._btns.index(self._current_active)
        return self._names[btn_idx]