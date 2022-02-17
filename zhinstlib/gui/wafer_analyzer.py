import numpy as np
from PyQt5.QtCore import pyqtSignal, pyqtSlot, QTimer, Qt
from PyQt5.QtWidgets import QMainWindow, QCheckBox, QWidget, QLabel, QGridLayout, QSpacerItem, QSizePolicy, QApplication
from PyQt5 import uic
import os
import sys
from pathlib import Path
from math import sqrt, floor
import pyqtgraph as pg
import re
import h5py
import time
import datetime

from zhinstlib.core.zinst_device import PyQtziVirtualDevice
from zhinstlib.core.custom_data_containers import LockinData
from zhinstlib.custom_widgets.wafer_dialogs import WaferDialogGui, ChooseModeDialog
from zhinstlib.custom_widgets.mouse_interacting_lineedit import InteractingLineEdit
from zhinstlib.custom_widgets.radio_btn_collection import RadioBtnList


class WaferAnalyzer(QMainWindow):
    signal_data_acquired = pyqtSignal()

    def __init__(self):
        super(WaferAnalyzer, self).__init__()
        self.this_dir = Path(__file__)
        ui_file = self.this_dir.parents[1] / 'ui_files' / 'wafer_analyzer.ui'
        uic.loadUi(ui_file, self)

        self.rows = 1
        self.cols = 1
        self.mode_num = 0
        self.wafer_name = ''
        self.wafer_directory = Path()
        self.demod_collection = [] #list to contain the demod checkbuttons
        self._creation_mode = False #Variable to communicate if the wafer is in wafer creation mode, or wafer loading mode
                                  #Determines if the Zurich is connected or not, plus some extra behaviours.
        self.active_mode = 0 #The mechanical mode currently checked.
        self.active_chip = '' #The name of the active chip
        self.loaded_data = dict() #The dictionary containing the loaded data. The keys correspond to the chip keys.
                                  #Each dictionary element is another dictionary, named after each mode.
        self._existing_chips = [] #This list will be filled in wafer loading mode. Disables the missing chip folders.
        self.zurich_id = ''

        #Setting and attributes used in the wafer creation mode
        self.zi_device = None
        self._saving_timeout = 2000
        self._daqmodule_name = None
        self._sig_paths = None
        self._temp_data = np.array([])
        self._current_savefile = Path()

        self._saving_timer = QTimer()
        self._saving_timer.timeout.connect(self.acquire_data)
        self.signal_data_acquired.connect(self.save_data, Qt.QueuedConnection)
        ######

        self.initUI()

    def initUI(self):
        self.open_mode_dialog()

        self.executionButton.set_onoff_strings(['Stop recording', 'Start recording'])

        btn_dictionary = {'R': self.rRadioBtn,
                          'phase': self.phaseRadioBtn,
                          'x':self.xRadioBtn,
                          'y': self.yRadioBtn}

        self.quadratureRadioButtons = RadioBtnList(**btn_dictionary)

        #Signal connections
        self.executionButton.toggled.connect(self.set_chip_interaction)
        self.refreshPlotsButton.clicked.connect(self.load_ringdowns)
        self.autorefreshCheckBox.stateChanged.connect(self.set_refreshbtn_status)
        self.modeSelector.currentIndexChanged.connect(self.set_active_mode)
        self.quadratureRadioButtons.btn_toggled.connect(self.test)
        self.quadratureRadioButtons.setChecked('R')

    def test(self, val):
        pass

    def open_mode_dialog(self):
        self.wafer_mode_selector = ChooseModeDialog()
        self.wafer_mode_selector.signal_wafer_mode.connect(self.set_wafer_mode_and_dir)
        self.wafer_mode_selector.show()

    def add_demodulators(self, demods):
        for demod in range(demods):
            chbox = QCheckBox()
            chbox.setText(str(demod + 1))
            self.demodContainer.addWidget(chbox)
            self.demod_collection.append(chbox)

    def add_wafer_layout(self):
        image_path = self.this_dir.parents[1] / 'artwork' / 'wafer.png'
        image_path = str(image_path).replace('\\', '/')
        style_command = f"QWidget#{self.backgroundWidget.objectName()} " + "{border-image:url(" + image_path + ")}"
        self.backgroundWidget.setStyleSheet(style_command)

        container_width = self.backgroundWidget.width()

        lateral_size = min(floor(0.65 * container_width / self.rows),
                                 floor(0.65 * container_width / self.cols))

        self.interactive_wafer = InteractiveWafer(self.rows, self.cols, lateral_size, active_chips=self._existing_chips)
        self.interactive_wafer.signal_id_changed.connect(self.set_active_chip)

        # If the wafer is in loading mode, then every time you click a chip, check how many modes there are and update
        # the combobox
        if self._creation_mode is False:
            self.interactive_wafer.signal_id_changed.connect(self.update_combobox_maxitems)
        self.plotContainer.addWidget(self.interactive_wafer)

        self.prepare_combobox()
        self.show()

    def set_active_chip(self, id):
        self.active_chip = id

    def call_wafer_creation_dialog(self):
        self._dialog = WaferDialogGui()
        self._dialog.dialog_accepted.connect(self.set_wafer_settings)
        self._dialog.rejected.connect(self.abort_window)
        self._dialog.show()

    def create_wafer_folder(self, directory, wafername, rows, cols, mode):
        if not isinstance(directory, Path):
            directory = Path(directory)

        try:
            (directory / wafername).mkdir(parents=False, exist_ok=False)
            with open(directory / wafername / 'wafer_info.txt', 'w') as file:
                todaysdate = datetime.date.today().strftime("%d/%m/%y")
                file.write(f"Date: {todaysdate}\nWafer name: {wafername}\nRows: {rows}\n"
                           f"Columns: {cols}\nMaximum mode number:{mode}\n"
                           f"Lock-in ID: {self.zurich_id}")
        except:
            print(f"Directory with name {wafername} in {directory} already exists. Operation aborted.")
            self.abort_window()

    def set_wafer_settings(self, rows, cols, mode_num, wafer_name, lockinID = None):
        self.rows = rows
        self.cols = cols
        self.mode_num = mode_num
        self.wafer_name = wafer_name
        self.zurich_id = lockinID

        if self._creation_mode:
            self.create_wafer_folder(self.wafer_directory, self.wafer_name,
                                     self.rows, self.cols, self.mode_num )
            self.connect_to_zurich(lockinID)
        self.add_wafer_layout()

    def connect_to_zurich(self, lockinID):
        try:
            self.zi_device = PyQtziVirtualDevice(lockinID)
        except:
            print(f"Failed connecting to {lockinID}. Aborted.")
            self.abort_window()
        demods = self.zi_device.get_available_demods()
        self.add_demodulators(demods)

        #Connect the signal required to stop or start the acquisition
        self.executionButton.clicked.connect(self.initialize_daq_module)
        self.executionButton.clicked.connect(self.stop_acquisition)

    def initialize_daq_module(self, buttonval):
        if buttonval is not True:
            return
        if self.active_chip: #If no chip is selected, the ID is the empty string
            saving_dir = self.wafer_directory / self.wafer_name / self.active_chip / f"mode{self.active_mode}"
            desired_signals = ['x', 'y', 'frequency']

            saving_kwargs = {'save_files': False,
                             'saving_onread':False
                             }
            stream_read_kwargs = {'read_duration': 9000,
                                  'burst_duration': 1}

            subscribe_demods = []
            for chbox in self.demod_collection:
                if chbox.isChecked():
                    subscribe_demods.append(int(chbox.text())-1)

            if len(subscribe_demods) == 0:
                print("You need to select at least a demodulator to start the acquisition.")
                self.executionButton.setChecked(False)
                return

            self._daqmodule_name, self._sig_paths = self.zi_device.set_subscribe_daq(subscribe_demods,
                                                                                    desired_signals,
                                                                                    **stream_read_kwargs,
                                                                                     **saving_kwargs)
            self._sig_paths = [path.lower() for path in self._sig_paths]

            ### Now create the saving folder if it doesn't exist
            saving_dir.mkdir(parents=True, exist_ok=True)

            ### Now create the h5 file. First get the h5 files in the folder, to pick the file name.
            file_num = len(list(saving_dir.glob('*h5')))
            file_num = str(file_num)
            ringdown_name = (4 - len(file_num)) * "0" + file_num  # Eg: file_num = 3, then ringdown_name = 0003
            self._current_savefile = saving_dir / f"ringdown{ringdown_name}.h5"
            with h5py.File(self._current_savefile, 'w') as h5file:
                h5kwargs = {'shape':(0,), 'maxshape': (None,), 'dtype':np.float32}
                for path in self._sig_paths:
                    h5file.create_dataset(name=path + '/timestamp', **h5kwargs)
                    h5file.create_dataset(name=path + '/value', **h5kwargs)

            ####Synchronize and start acquisition
            self.zi_device.sync()
            self.zi_device.execute_daqmodule(self._daqmodule_name)
            self._saving_timer.start(self._saving_timeout)
        else:
            self.executionButton.setChecked(False)

    def acquire_data(self):
        self._temp_data = self.zi_device.daqmodules[self._daqmodule_name].read(True)
        self.signal_data_acquired.emit()

    def save_data(self):
        returned_sig_paths = [signal_path.lower() for signal_path in self._temp_data.keys()]
        with h5py.File(self._current_savefile, 'a') as file:
            for signal_path in self._sig_paths:
                if signal_path in returned_sig_paths:
                    #If the subscribed signal is present in the read data paths, read it, and then append it to the
                    #h5 file.
                    for ii, signal_burst in enumerate(self._temp_data[signal_path.lower()]):
                        time_ax = signal_burst["timestamp"][0, :]
                        value = signal_burst["value"][0, :]

                        dset_time = file[signal_path + '/timestamp']
                        dset_value = file[signal_path + '/value']

                        dset_time.resize( (dset_time.shape[0] + len(time_ax), ) )
                        dset_value.resize( (dset_value.shape[0] + len(value), ) )

                        dset_time[-len(time_ax):] = time_ax
                        dset_value[-len(value):] = value

    def stop_acquisition(self, buttonval):
        if buttonval is False and self.active_chip:
            if self._daqmodule_name:
                self.zi_device.stop_daqmodule(self._daqmodule_name)
                #Read one last time
                self.save_data()
                self._saving_timer.stop()
            self._daqmodule_name = None
            self._sig_paths = None
            self._temp_data = np.array([])
            self._current_savefile = Path()

    def set_wafer_mode_and_dir(self, directory, mode):
        if not isinstance(directory, Path):
            directory = Path(directory)
        self.wafer_directory = directory
        self._creation_mode = mode

        if self._creation_mode:
            self.call_wafer_creation_dialog()
        else:
            self.executionButton.setEnabled(False)
            self.get_wafer_info(self.wafer_directory)

    def get_wafer_info(self, directory):
        """
        Called when loading an existing wafer
        """
        if not isinstance(directory, Path):
            directory = Path(directory)

        with open(directory / 'wafer_info.txt', 'r') as file:
            for line in file.readlines():
                if "Rows" in line:
                    chip_rows = int(line.split(":")[1].strip())
                elif "Columns" in line:
                    chip_cols = int(line.split(":")[1].strip())
                elif "Maximum mode number" in line:
                    max_mode = int(line.split(":")[1].strip())
                elif "Lock-in ID" in line:
                    zurich_id = line.split(":")[1].strip()
        #Get the existing folders, and append them to the existing_chips attribute
        pattern = r"([A-Z])(\d+)"
        for directory_content in directory.iterdir():
            if directory_content.is_dir():
                match = re.match(pattern, directory_content.name)
                if match is not None:
                    self._existing_chips.append(match.group(0))

        self.set_wafer_settings(chip_rows, chip_cols, max_mode, directory.name, zurich_id)

    def prepare_combobox(self):
        base_string = "Mode {:d}"
        for ii in range(self.mode_num):
            self.modeSelector.addItem(base_string.format(ii + 1), ii)

    def update_combobox_maxitems(self, id):
        """
        This function gets called when the wafer is in loading mode. It looks into the folder contents and updates the
        maximum visible items in the comboxbox
        """
        direc = self.wafer_directory / id
        pattern = "mode(\d+)"

        modes_in_folder = []
        for mode_folder in direc.iterdir():
            match = re.match(pattern, mode_folder.name)
            if mode_folder.is_dir() and match is not None:
                modes_in_folder.append(int(match.group(1))-1)

        for ii in range(self.mode_num):
            if ii in modes_in_folder:
                setenbl = True
            else:
                setenbl = False
            self.modeSelector.model().item(ii).setEnabled(setenbl)

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

    def load_ringdowns(self):
        active_name = self.interactive_wafer.current_active

        if active_name is not None:
            ringdown_path = self.wafer_directory / active_name / f"mode{self.active_mode}"
            basepath = f'{self.zurich_id}/demods'
            if active_name not in self.loaded_data.keys():
                mode_dictionary = dict()
                self.loaded_data[active_name] = mode_dictionary
            elif self.active_mode in self.loaded_data[active_name].keys():
                print("Data already in memory.")
                return
            else:
                mode_dictionary = self.loaded_data[active_name]

            ringdown_list = []
            for ringdown in ringdown_path.glob('*h5'):
                ringdown_li_data = LockinData()
                with h5py.File(ringdown, 'r') as file:
                    demod_num = len(file[basepath].keys())
                    for demod in range(demod_num):
                        timestamp = file[basepath + f"/{demod}/sample.frequency/timestamp"][:]
                        timestamp = (timestamp - timestamp[0]) / 210e6

                        frequency = file[basepath + f"/{demod}/sample.frequency/value"][:].mean()
                        x_quad = file[basepath + f"/{demod}/sample.x/value"][:]
                        y_quad = file[basepath + f"/{demod}/sample.y/value"][:]

                        ringdown_li_data.create_demod(demod, time_axis=timestamp, x_quad=x_quad, y_quad=y_quad,
                                                      frequency=frequency)

                ringdown_list.append(ringdown_li_data)

            mode_dictionary[self.active_mode] = ringdown_list

            self.refresh_plot()

    def refresh_plot(self):
        pass

    def abort_window(self):
        sys.exit()

class InteractiveWafer(QWidget):

    signal_id_changed = pyqtSignal(str)

    def __init__(self, rows=1, cols=1, fixed_size=100, active_chips = [], *args, **kwargs):
        super(InteractiveWafer, self).__init__()
        self.rows = rows
        self.cols = cols
        self.fixed_size = fixed_size #The size of the square side
        self.active_chips = active_chips #Determines which chip is interacting. If [], the all are interactive.
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
                    layout.addWidget(widgy, ii + 1, jj, Qt.AlignVCenter)

                    # This widget is used for centering purposes
                    widgy = QLabel(str(ii))
                    widgy.setStyleSheet("font-weight: bold; color:rgba(0,0,0,0)")
                    layout.addWidget(widgy, ii + 1, jj + self.cols + 1, Qt.AlignVCenter)
                if ii == 1:
                    widgy = QLabel(chr(ord('A') + jj - 1))
                    widgy.setStyleSheet("font-weight: bold;")
                    layout.addWidget(widgy, ii, jj + 1, Qt.AlignHCenter)

                    # This widget is used for centering purposes
                    widgy = QLabel(chr(ord('A') + jj - 1))
                    widgy.setStyleSheet("font-weight: bold; color:rgba(0,0,0,0)")
                    layout.addWidget(widgy, ii + self.rows + 1, jj + 1, Qt.AlignHCenter)

        for ii in range(2, self.rows + 2):
            for jj in range(2, self.cols + 2):
                if (ii != 2 and ii != self.rows + 1) or (jj != 2 and jj != self.cols + 1):
                    temp_id = chr(ord('A') + jj - 2) + str(ii-1)
                    widgy = InteractingLineEdit(temp_id, self.fixed_size)
                    self.chip_collection[temp_id] = widgy
                    widgy.signal_widget_clicked.connect(self.update_square)
                    #Here determine if after loading, the chip will be interactive or not
                    if len(self.active_chips) > 0 and temp_id not in self.active_chips:
                        widgy.interaction_enabled(False)
                        widgy.set_active_stylesheet("data missing")
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
        if not self.current_active:
            self.current_active = id
        elif self.current_active != id:
            self.chip_collection[self.current_active].unclick()
            self.current_active = id
        elif self.current_active == id:
            self.current_active = ''
        self.signal_id_changed.emit(self.current_active)

if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = WaferAnalyzer()
    sys.exit(app.exec_())
    # sys.exit()