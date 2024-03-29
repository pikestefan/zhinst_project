from PyQt5.QtWidgets import QDialog, QFileDialog
from PyQt5 import uic
from PyQt5.QtCore import pyqtSignal
from pathlib import Path
import os


class ChooseModeDialog(QDialog):
    signal_wafer_mode = pyqtSignal(str, int)
    signal_mode_closed = pyqtSignal()

    """
    Three values: 0-> Create new directory, 1->Append to existing, 2->Load data
    """

    def __init__(self):
        this_dir = Path(__file__).resolve()
        ui_file = this_dir.parents[1] / "ui_files" / "wafer_folder_selection.ui"
        super(ChooseModeDialog, self).__init__()
        uic.loadUi(ui_file, self)

        self.createButton.clicked.connect(self.create_load)
        self.loadButton.clicked.connect(self.create_load)
        self.appendButton.clicked.connect(self.create_load)

        self._dialog = QFileDialog()

    def create_load(self, val):
        options = self._dialog.Options()
        foldername = self._dialog.getExistingDirectory(
            self, "QFileDialog.getOpenFileName()", "", options=options
        )
        sender_name = self.sender().objectName()
        if sender_name == "createButton":
            create_val = 0
        elif sender_name == "loadButton":
            create_val = 2
        else:
            create_val = 1

        if foldername != "":
            self.signal_wafer_mode.emit(foldername, create_val)
            self.close()


class WaferDialogGui(QDialog):
    dialog_accepted = pyqtSignal(int, int, int, str, str)

    def __init__(self):
        this_dir = Path(__file__).resolve()
        ui_file = this_dir.parents[1] / "ui_files" / "wafer_dialog.ui"
        super(WaferDialogGui, self).__init__()
        uic.loadUi(str(ui_file), self)

        rows = self.rowsBox.setValue(5)
        cols = self.colsBox.setValue(5)
        modes = self.modeNumber.setValue(1)

        self.buttonBox.accepted.connect(self.return_spinbox_vals)
        self.show()

    def return_spinbox_vals(self):
        rows = self.rowsBox.value()
        cols = self.colsBox.value()
        modes = self.modeNumber.value()
        wafer_name = self.waferName.text()
        lockinID = self.lockinID.text()
        self.dialog_accepted.emit(rows, cols, modes, wafer_name, lockinID)
