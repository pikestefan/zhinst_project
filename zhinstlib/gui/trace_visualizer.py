from PyQt5 import QtCore, QtWidgets, uic
import os
from pathlib import Path
import sys


class test_window(QtWidgets.QMainWindow):
    def __init__(self):
        super(test_window, self).__init__()
        this_dir = Path(__file__).parents[1]
        ui_file = this_dir / "ui_files" / "trace_viewer.ui"
        uic.loadUi(ui_file, self)
        self.show()


if __name__ == "__main__":
    app = QtWidgets.QApplication(sys.argv)
    window = test_window()
    app.exec_()
