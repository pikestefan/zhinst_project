import numpy as np
from PyQt5 import QtCore as qcore
from PyQt5.QtCore import pyqtSignal, pyqtSlot
from PyQt5.QtWidgets import QMainWindow, QCheckBox, QWidget, QLabel, QGridLayout, QSpacerItem, QSizePolicy, QApplication
from PyQt5 import uic
import os
import sys
from pathlib import Path
from math import sqrt, floor
import pyqtgraph as pg
import re
import h5py

from zhinstlib.core.zinst_device import ziVirtualDevice
from zhinstlib.core.custom_data_containers import LockinData
from zhinstlib.custom_widgets.wafer_dialogs import WaferDialogGui, ChooseModeDialog
from zhinstlib.custom_widgets.mouse_interacting_lineedit import InteractingLineEdit
from zhinstlib.custom_widgets.radio_btn_collection import RadioBtnList


class WaferAnalyzer(QMainWindow):

    def __init__(self):
        super(WaferAnalyzer, self).__init__()
        self.this_dir = Path(os.path.dirname(__file__))
        ui_file = self.this_dir.parents[0] / 'ui_files' / 'wafer_analyzer.ui'
        uic.loadUi(ui_file, self)

        self.rows = 1
        self.cols = 1
        self.mode_num = 0
        self.wafer_name = ''
        self.wafer_directory = Path()
        self.demod_collection = []
        self._create_mode = False
        self.active_mode = 0
        self.loaded_data = dict()
        self.zi_device = None

        self.initUI()

    def initUI(self):
        self.open_mode_dialog()

        self.executionButton.set_onoff_strings(['Stop recording', 'Start recording'])
        self.executionButton.clicked.connect(self.set_chip_interaction)
        self.autorefreshCheckBox.stateChanged.connect(self.set_refreshbtn_status)

        self.modeSelector.currentIndexChanged.connect(self.set_active_mode)


        btn_dictionary = {'R': self.rRadioBtn,
                          'phase': self.phaseRadioBtn,
                          'x':self.xRadioBtn,
                          'y': self.yRadioBtn}

        self.quadratureRadioButtons = RadioBtnList(**btn_dictionary)
        self.quadratureRadioButtons.btn_toggled.connect(self.test)
        self.quadratureRadioButtons.setChecked('R')

        self.refreshPlotsButton.clicked.connect(self.load_ringdowns)

    def test(self, val):
        pass

    def open_mode_dialog(self):
        self.wafer_mode_selector = ChooseModeDialog()
        self.wafer_mode_selector.signal_wafer_mode.connect(self.set_mode_and_dir)
        self.wafer_mode_selector.show()

    def add_demodulators(self):
        demods = self.get_demod_num()
        for demod in range(demods):
            chbox = QCheckBox()
            chbox.setText(str(demod + 1))
            self.demodContainer.addWidget(chbox)

    def add_wafer_layout(self):
        image_path = self.this_dir.parents[0] / 'artwork' / 'wafer.png'
        image_path = str(image_path).replace('\\', '/')
        style_command = f"QWidget#{self.backgroundWidget.objectName()} " + "{border-image:url(" + image_path + ")}"
        self.backgroundWidget.setStyleSheet(style_command)

        container_width = self.backgroundWidget.width()

        lateral_size = min(floor(0.65 * container_width / self.rows),
                                 floor(0.65 * container_width / self.cols))

        self.interactive_wafer = InteractiveWafer(self.rows, self.cols, lateral_size)
        self.plotContainer.addWidget(self.interactive_wafer)

        self.prepare_combobox()

        self.show()

    def get_demod_num(self):
        # FIXME: for now return just a fixed number
        return 6

    def call_wafer_creation_dialog(self):
        self._dialog = WaferDialogGui()
        self._dialog.dialog_accepted.connect(self.set_wafer_matrix)
        self._dialog.rejected.connect(self.abort_window)
        self._dialog.show()

    def create_wafer_folder(self, directory, wafername, rows, cols, modes):
        if not isinstance(directory, Path):
            directory = Path(directory)

        try:
            (directory / wafername).mkdir(parents=False, exist_ok=False)
        except:
            print(f"Directory with name {wafername} in {directory} already exists. Operation aborted.")
            self.abort_window()

        for ii in range(1, rows + 1):
            for jj in range(1, cols + 1):
                folder_id = chr(ord('A') + jj - 1) + str(ii)
                (directory / wafername / folder_id).mkdir(parents=False)
                for mode_num in range(1, modes + 1):
                    (directory / wafername / folder_id / f"mode{mode_num}").mkdir(parents=False)

    def set_wafer_matrix(self, rows, cols, mode_num, wafer_name, lockinID = None):
        self.rows = rows
        self.cols = cols
        self.mode_num = mode_num
        self.wafer_name = wafer_name

        if self._create_mode:
            self.create_wafer_folder(self.wafer_directory, self.wafer_name,
                                     self.rows, self.cols, self.mode_num)
            self.connect_to_zurich(lockinID)
        self.add_wafer_layout()

    def connect_to_zurich(self, lockinID):
        self.zi_device = ziVirtualDevice(lockinID)
        print("testing")

    def set_mode_and_dir(self, directory, mode):
        if not isinstance(directory, Path):
            directory = Path(directory)
        self.wafer_directory = directory
        self._create_mode = mode

        if self._create_mode:
            self.call_wafer_creation_dialog()
            self.add_demodulators() #Placeholder: need to connect to the Zurich at some point
        else:
            self.executionButton.setEnabled(False)
            self.get_wafer_info(self.wafer_directory)

    def get_wafer_info(self, directory):
        if not isinstance(directory, Path):
            directory = Path(directory)

        chip_pattern = r"([a-zA-Z])(\d+)"
        mode_pattern = r"mode(\d+)"

        chip_rows = []
        chip_cols = []
        mode_nums = []
        for subdir in directory.iterdir():
            mode_num = 0
            match = re.match(chip_pattern, subdir.name)
            if match is None:
                print(f"Directory contents are invalid. Folder content must be <letter><number>. Failed at {subdir}. Aborting.")
                self.abort_window()
                return
            else:
                chip_col_letter = match.group(1)
                chip_row_letter = match.group(2)
                if chip_row_letter not in chip_rows:
                    chip_rows.append(chip_row_letter)
                if chip_col_letter not in chip_cols:
                    chip_cols.append(chip_col_letter)
            for mode_dir in subdir.iterdir():
                match = re.match(mode_pattern, mode_dir.name)
                if match is None:
                    print(f"Directory contents are invalid. Folder formate must be mode<number>Failed at {mode_dir} Aborting.")
                    self.abort_window()
                    return
                else:
                    mode_num += 1
            mode_nums.append(mode_num)
        if len(np.unique(mode_nums)) != 1:
            print("Some folders contain more modes than others. Aborting.")
            self.abort_window()
            return
        else:
            self.set_wafer_matrix(len(chip_rows), len(chip_cols), mode_nums[0], directory.name )

    def prepare_combobox(self):
        base_string = "Mode {:d}"
        for ii in range(self.mode_num):
            self.modeSelector.addItem(base_string.format(ii + 1), ii)

    def set_chip_interaction(self, value):
        for chip in self.interactive_wafer.chip_collection.values():
            chip.interaction_enabled(not value)

    def set_refreshbtn_status(self, checkval):
        curr_act = self.interactive_wafer.current_active
        if checkval == 2:
            enabled_state = False
            self.interactive_wafer.signal_id_changed.connect(self.load_ringdowns)
        else:
            enabled_state = True
            self.interactive_wafer.signal_id_changed.disconnect()
        if curr_act is not None:
            self.interactive_wafer.chip_collection[curr_act].unclick()
        self.refreshPlotsButton.setEnabled(enabled_state)

    def set_active_mode(self, val):
        self.active_mode = val+1


    def refresh_plot(self, id):
        if id is None:
            pass
        else:
            print(id)

    def load_ringdowns(self):
        active_name = self.interactive_wafer.current_active
        if active_name is not None:
            ringdown_path = self.wafer_directory / active_name / f"mode{self.active_mode}"
            #########
            ####This section is temporary
            #########
            basepath = '000/dev1347/demods'
            ringdown_data = dict()
            ringdown_num = 0

            if len([_ for _ in ringdown_path.glob('*h5')]) > 0:
                for chip_content in ringdown_path.glob('*h5'):
                    demod_num = 0
                    ringdown_li_data = LockinData()
                    with h5py.File(chip_content, 'r') as file:
                        demod_num = len(file[basepath])
                        for demod in range(demod_num):
                            frequency = file[basepath + f"/{demod}/sample/frequency"][:].mean()
                            time_axis = file[basepath + f"/{demod}/sample/timestamp"][:]
                            time_axis = (time_axis - time_axis[0]) / 210e6
                            x_quad = file[basepath + f"/{demod}/sample/x"][:]
                            y_quad = file[basepath + f"/{demod}/sample/x"][:]

                            ringdown_li_data.create_demod(demod, time_axis, x_quad, y_quad, frequency)
                    ringdown_data[ringdown_num] = ringdown_li_data
                self.loaded_data[active_name] = ringdown_data
            else:
                print("Empty directory")

    def abort_window(self):
        sys.exit()

class InteractiveWafer(QWidget):
    signal_id_changed = pyqtSignal(str)
    def __init__(self, rows=1, cols=1, fixed_size=100, *args, **kwargs):
        super(InteractiveWafer, self).__init__()
        this_dir = Path(os.path.dirname(__file__))
        self.rows = rows
        self.cols = cols
        self.fixed_size = fixed_size
        self.chip_collection = dict()
        self.do_grid()
        self.current_active = None
        self.setAutoFillBackground(False)

    def do_grid(self):
        layout = QGridLayout()
        self.setLayout(layout)

        for ii in range(1, self.rows + 1):
            for jj in range(1, self.cols + 1):
                if jj == 1:
                    widgy = QLabel(str(ii))
                    widgy.setStyleSheet("font-weight: bold;")
                    layout.addWidget(widgy, ii + 1, jj, qcore.Qt.AlignVCenter)

                    # This widget is used for centering purposes
                    widgy = QLabel(str(ii))
                    widgy.setStyleSheet("font-weight: bold; color:rgba(0,0,0,0)")
                    layout.addWidget(widgy, ii + 1, jj + self.cols + 1, qcore.Qt.AlignVCenter)
                if ii == 1:
                    widgy = QLabel(chr(ord('A') + jj - 1))
                    widgy.setStyleSheet("font-weight: bold;")
                    layout.addWidget(widgy, ii, jj + 1, qcore.Qt.AlignHCenter)

                    # This widget is used for centering purposes
                    widgy = QLabel(chr(ord('A') + jj - 1))
                    widgy.setStyleSheet("font-weight: bold; color:rgba(0,0,0,0)")
                    layout.addWidget(widgy, ii + self.rows + 1, jj + 1, qcore.Qt.AlignHCenter)

        for ii in range(2, self.rows + 2):
            for jj in range(2, self.cols + 2):
                if (ii != 2 and ii != self.rows + 1) or (jj != 2 and jj != self.cols + 1):
                    temp_id = chr(ord('A') + jj - 2) + str(ii-1)
                    widgy = InteractingLineEdit(temp_id, self.fixed_size)
                    self.chip_collection[temp_id] = widgy
                    widgy.signal_widget_clicked.connect(self.update_square)
                    layout.addWidget(widgy, ii, jj)

        #Add four spacers on the four square corners to center the chips
        hor_spacer = QSpacerItem(40, 20, QSizePolicy.Expanding, QSizePolicy.Minimum)
        ver_spacer = QSpacerItem(20, 40, QSizePolicy.Minimum, QSizePolicy.Expanding)

        layout.addItem(hor_spacer, 1, 0)
        layout.addItem(hor_spacer, 1, self.cols + 3)
        layout.addItem(ver_spacer, 0, 1)
        layout.addItem(ver_spacer, self.rows + 3, 1)
        layout.setHorizontalSpacing(3)
        layout.setVerticalSpacing(3)

    def update_square(self, id):
        if self.current_active is None:
            self.current_active = id
        elif self.current_active != id:
            self.chip_collection[self.current_active].unclick()
            self.current_active = id
        elif self.current_active == id:
            self.current_active = None
        self.signal_id_changed.emit(self.current_active)

if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = WaferAnalyzer()
    sys.exit(app.exec_())
    # sys.exit()