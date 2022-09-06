from PyQt5 import QtCore as qcore
from PyQt5.QtCore import pyqtSignal, pyqtSlot
from PyQt5 import QtGui as qgui
from PyQt5 import QtWidgets as qwid


class ButtonText(qwid.QPushButton):
    def __init__(self, *args, **kwargs):
        super(ButtonText, self).__init__(*args, **kwargs)
        self.setCheckable(True)
        self.on_off_strings = ["on", "off"]
        self.setChecked(False)
        self.set_onoff_strings(self.on_off_strings)
        self.clicked.connect(self.change_text)
        self.toggled.connect(self.change_text)

    def change_text(self):
        if self.isChecked():
            self.setText(self.on_off_strings[0])
        else:
            self.setText(self.on_off_strings[1])

    def set_onoff_strings(self, string_array):
        self.on_off_strings = string_array
        self.change_text()
