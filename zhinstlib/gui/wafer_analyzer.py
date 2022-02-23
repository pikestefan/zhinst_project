import numpy as np
from PyQt5.QtCore import pyqtSignal, pyqtSlot, QTimer, Qt
from PyQt5.QtWidgets import QMainWindow, QCheckBox, QApplication, QButtonGroup
from PyQt5 import uic
import os
import sys
from pathlib import Path
from math import sqrt, floor
import pyqtgraph as pg
import re
import h5py
import datetime
from operator import itemgetter

from zhinstlib.core.zinst_device import PyQtziVirtualDevice
from zhinstlib.core.custom_data_containers import LockinData, RingdownContainer, WaferContainer
from zhinstlib.custom_widgets.wafer_dialogs import WaferDialogGui, ChooseModeDialog
from zhinstlib.custom_widgets.interactive_wafer import InteractiveWafer
from zhinstlib.helpers.characterization_helpers import create_wafer


class WaferAnalyzer(QMainWindow):
    signal_data_acquired = pyqtSignal()
    signal_data_saved = pyqtSignal(float)
    signal_data_uploaded = pyqtSignal(str)

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
        self.wafer_list = [] #A list of wafer "slices". Each slice corresponds to a mechanical mode.
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
        self.signal_data_saved.connect(self.display_file_size, Qt.QueuedConnection)
        self.signal_data_uploaded.connect(self.set_loaded_cell_style, Qt.QueuedConnection)
        self.actionExportMode.triggered.connect(self.export_data)
        ######

        self.initUI()

    def initUI(self):
        self.open_mode_dialog()

        self.executionButton.set_onoff_strings(['Stop recording', 'Start recording'])

        self.quadratureRadioButtons = QButtonGroup()
        for ii, btn in enumerate([self.xRadioBtn, self.yRadioBtn, self.rRadioBtn, self.phaseRadioBtn]):
            self.quadratureRadioButtons.addButton(btn)
            self.quadratureRadioButtons.setId(btn, ii)

        self.rRadioBtn.setChecked(True)

        self.linlogRadioButtons = QButtonGroup()
        for ii, btn in enumerate([self.linScaleRadioBtn, self.logScaleRadioBtn]):
            self.linlogRadioButtons.addButton(btn)
            self.linlogRadioButtons.setId(btn, ii)
        self.linScaleRadioBtn.setChecked(True)

        self.actionRadioButtons = QButtonGroup()
        for ii, btn in enumerate([self.selRdownBtn, self.selChipBtn, self.selWaferBtn]):
            self.actionRadioButtons.addButton(btn)
            self.actionRadioButtons.setId(btn, ii)
        self.selRdownBtn.setChecked(True)

        self.data_plot = pg.PlotDataItem(pen = pg.mkPen(width = 1, color = 'w'))
        self.fit_plot = pg.PlotDataItem(pen = pg.mkPen(width = 1, color = 'r'))
        self.dataPlotWidget.addItem(self.data_plot)
        self.dataPlotWidget.addItem(self.fit_plot)

        #Signal connections
        self.executionButton.toggled.connect(self.set_chip_interaction)
        self.loadSelectedButton.clicked.connect(self.load_single_ringdown)
        self.loadAllButton.clicked.connect(self.load_all_chip_ringdowns)
        self.modeSelector.currentIndexChanged.connect(self.set_active_mode)
        self.quadratureRadioButtons.buttonToggled.connect(self.refresh_plot)
        self.ringdownSpinBox.valueChanged.connect(self.update_plotting_demod_comboboxes)
        self.linlogRadioButtons.buttonToggled.connect(self.set_linlogscale)
        self.demodComboBox.currentIndexChanged.connect(self.refresh_plot)
        self.clearSelectedMemoryBtn.clicked.connect(self.clear_memory_selected)
        self.clearAllMemoryBtn.clicked.connect(self.clear_memory)
        self.chunkifyBtn.clicked.connect(self.chunkify_data)
        self.fitBtn.clicked.connect(self.fit_data)

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
        lateral_size = self.set_wafer_widg_background()
        self.interactive_wafer = InteractiveWafer(self.rows, self.cols, lateral_size)
        self.interactive_wafer.signal_id_changed.connect(self.set_active_chip)
        self.plotContainer.addWidget(self.interactive_wafer)

        if self._creation_mode is False:
            self.create_wafer_container_list(self.wafer_directory / self.wafer_name)

        self.prepare_demodulatorselection_combobox()
        self.show()

    def set_wafer_widg_background(self):
        image_path = self.this_dir.parents[1] / 'artwork' / 'wafer.png'
        image_path = str(image_path).replace('\\', '/')
        style_command = f"QWidget#{self.backgroundWidget.objectName()} " + "{border-image:url(" + image_path + ")}"
        self.backgroundWidget.setStyleSheet(style_command)

        container_width = self.backgroundWidget.width()
        lateral_size = min(floor(0.7 * container_width / self.rows),
                           floor(0.7 * container_width / self.cols))
        return lateral_size

    def create_wafer_container_list(self, directory):
        """
        :param directory: the directory of the wafer
        """
        for mode in range(self.mode_num):
            wcont = WaferContainer(mode)
            self.wafer_list.append(wcont)

        pattern_chip = r"([A-Z])(\d+)"
        pattern_mode = r"mode(\d+)"
        for wafer_directory_content in directory.iterdir():
            if wafer_directory_content.is_dir():
                match = re.match(pattern_chip, wafer_directory_content.name)
                if match is not None:
                    chipID = match.group(0)
                    for chip_directory_content in wafer_directory_content.iterdir():
                        match = re.match(pattern_mode, chip_directory_content.name )
                        if match is not None:
                            mode_num = int(match.group(1)) - 1
                            self.wafer_list[mode_num].add_available_chip(chipID)

    def set_active_chip(self, id):
        self.active_chip = id
        self.update_spinbox()
        self.refresh_plot()

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
            saving_dir = self.wafer_directory / self.wafer_name / self.active_chip / f"mode{self.active_mode+1}"
            desired_signals = ['x', 'y', 'frequency']

            saving_kwargs = {'save_files': False,
                             'saving_onread':False
                             }
            stream_read_kwargs = {'read_duration': 9000,
                                  'burst_duration': 0.5}

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
                h5kwargs = {'shape':(0,), 'maxshape': (None,), 'dtype':np.float64}
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
        if isinstance(self._temp_data, dict):
            returned_sig_paths = [signal_path.lower() for signal_path in self._temp_data.keys()]
        else:
            return

        for signal_path in self._sig_paths:
            if signal_path in returned_sig_paths:
                #If the subscribed signal is present in the read data paths, read it, and then append it to the
                #h5 file.
                time_ax_tot, value_tot = np.array([]), np.array([])
                for ii, signal_burst in enumerate(self._temp_data[signal_path.lower()]):
                    time_ax = signal_burst["timestamp"][0, :]
                    value = signal_burst["value"][0, :]

                    time_ax_tot = np.concatenate((time_ax_tot, time_ax))
                    value_tot = np.concatenate((value_tot, value))

                with h5py.File(self._current_savefile, 'a') as file:
                    dset_time = file[signal_path + '/timestamp']
                    dset_value = file[signal_path + '/value']

                    dset_time.resize((dset_time.shape[0] + len(time_ax_tot),))
                    dset_value.resize((dset_value.shape[0] + len(value_tot),))

                    dset_time[-len(time_ax_tot):] = time_ax_tot
                    dset_value[-len(value_tot):] = value_tot

        filesizeMb = self._current_savefile.stat().st_size / 1e6
        self.signal_data_saved.emit(filesizeMb)

    def stop_acquisition(self, buttonval):
        if buttonval is False and self.active_chip:
            if self._daqmodule_name:
                self.zi_device.stop_daqmodule(self._daqmodule_name)
                #Read one last time
                self.zi_device.remove_daqmodule(self._daqmodule_name)
                self._saving_timer.stop()
            self._daqmodule_name = None
            self._sig_paths = None
            self._temp_data = np.array([])
            self._current_savefile = Path()

    def set_wafer_mode_and_dir(self, directory, mode):
        if not isinstance(directory, Path):
            directory = Path(directory)
        self._creation_mode = mode

        if self._creation_mode:
            self.call_wafer_creation_dialog()
            self.wafer_directory = directory
        else:
            self.executionButton.setEnabled(False)
            self.get_wafer_info(directory)

    def get_wafer_info(self, directory):
        """
        Called when loading an existing wafer
        """
        with open(directory /'wafer_info.txt', 'r') as file:
            for line in file.readlines():
                if "Rows" in line:
                    chip_rows = int(line.split(":")[1].strip())
                elif "Columns" in line:
                    chip_cols = int(line.split(":")[1].strip())
                elif "Maximum mode number" in line:
                    max_mode = int(line.split(":")[1].strip())
                elif "Lock-in ID" in line:
                    zurich_id = line.split(":")[1].strip()

        self.wafer_directory = directory.parents[0]
        self.set_wafer_settings(chip_rows, chip_cols, max_mode, directory.name, zurich_id)

    def prepare_demodulatorselection_combobox(self):
        base_string = "Mode {:d}"
        for ii in range(self.mode_num):
            self.modeSelector.addItem(base_string.format(ii + 1), ii)

    def set_chip_interaction(self, value):
        for chip in self.interactive_wafer.chip_collection.values():
            chip.set_interacting(not value)

    def set_active_mode(self, val):
        self.active_mode = val
        self.update_wafer_image()

    def update_wafer_image(self):
        active_wafer =  self.wafer_list[self.active_mode]
        available_chips = active_wafer.get_available_chips()
        loaded_chips = active_wafer.get_loaded_chips()

        for chipID, chip in self.interactive_wafer.chip_collection.items():
            if (chipID == self.active_chip) and chip.isclicked:
                chip.unclick()
            if chipID not in available_chips:
                chip.setActivated(False)
            else:
                chip.setActivated(True)

            if chipID in loaded_chips:
                chip.setDataUploaded(True)
            else:
                chip.setDataUploaded(False)

            self.set_chip_info(chipID)

    def load_all_chip_ringdowns(self):
        for chipID, cell in self.interactive_wafer.chip_collection.items():
            if cell.isActivated() and not cell.hasData():
                self.load_ringdowns(chipID, self.active_mode)

    def load_single_ringdown(self):
        if self.active_chip == '':
            print("No chip selected.")
            return

        self.load_ringdowns(self.active_chip, self.active_mode)

    def load_ringdowns(self, active_chip, active_mode):

        ringdown_path = self.wafer_directory / self.wafer_name / active_chip / f"mode{active_mode+1}"
        basepath = f'{self.zurich_id}/demods'
        ringdowns_in_path = list(ringdown_path.glob('*h5'))

        if len(ringdowns_in_path) == 0:
            print("No data in the folder.")
            return

        current_wafer = self.wafer_list[active_mode]

        #TODO: add a step to check for the number of ringdowns in a mode. If in the folder there are more than loaded, add them

        if active_chip in current_wafer.get_loaded_chips():
            print("Data already in memory.")
            return
        else:
            ringdown_collection = RingdownContainer()
            for ringdown in ringdowns_in_path:
                ringdown_collection.load_ringdown(ringdown, basepath)

            current_wafer.add_ringdowns(active_chip, ringdown_collection)

            self.update_spinbox()
            self.signal_data_uploaded.emit(active_chip)

    def update_spinbox(self):
        """
        Called when loading new data, when clicking the mode selector, and when selecting a new chip.
        """
        if self.chipandmode_areLoaded(self.active_chip, self.active_mode):
            ringdown_container = self.wafer_list[self.active_mode].get_ringdowns(self.active_chip)
            self.ringdownSpinBox.setMaximum(ringdown_container.get_ringdown_num())
            if self.ringdownSpinBox.value()==1:
                self.ringdownSpinBox.valueChanged.emit(1)
            else:
                self.ringdownSpinBox.setValue(1)

    def update_plotting_demod_comboboxes(self, selected_ringdown):
        """
        Called when loading new data, when clicking the mode selector, when selecting a new chip, and when changin the ringdown.
        """
        for combobox in [self.demodComboBox, self.referenceDemodComboBox, self.fitDemodComboBox]:
            previous_text = combobox.currentText()
            if self.chipandmode_areLoaded(self.active_chip, self.active_mode):
                ringdown_container = self.wafer_list[self.active_mode].get_ringdowns(self.active_chip)
                combobox.blockSignals(True)
                combobox.clear()
                availdemodlist = ringdown_container.get_ringdown_demods(selected_ringdown-1) #-1 because of python indexing
                for demod in availdemodlist:
                    combobox.addItem(str(demod+1))

                idx = combobox.findText(previous_text)
                if idx == -1: #meaning that the search has failed:
                    #Return the first element of the avaiable demods
                    idx = combobox.findText(str(availdemodlist[0] + 1))
                combobox.setCurrentIndex(idx)
                combobox.blockSignals(False)
                combobox.currentIndexChanged.emit(idx)

    def refresh_plot(self):
        if self.chipandmode_areLoaded(self.active_chip, self.active_mode):
            ringdown_container = self.wafer_list[self.active_mode].get_ringdowns(self.active_chip)
            curr_rdown = self.ringdownSpinBox.value() - 1 #Always translate user-friendly data to python indices

            curr_demod = int(self.demodComboBox.currentText()) - 1
            rdown_data = ringdown_container.ringdown(curr_rdown).demod(curr_demod)

            requested_quad = self.quadratureRadioButtons.checkedId()

            timestamp = rdown_data.time_axis
            if requested_quad == 2:
                plot_quad = rdown_data.r_quad
                self.dataPlotWidget.setLabel('left', 'Amplitude (V)')
            elif requested_quad == 0:
                plot_quad = rdown_data.x_quad
                self.dataPlotWidget.setLabel('left', 'Amplitude (V)')
            elif requested_quad == 1:
                plot_quad = rdown_data.y_quad
                self.dataPlotWidget.setLabel('left', 'Amplitude (V)')
            elif requested_quad == 3:
                plot_quad = rdown_data.phase_quad
                self.dataPlotWidget.setLabel('left', 'Phase (rad)')
            self.dataPlotWidget.setLabel('bottom', 'Time (s)')

            self.dataPlotWidget.disableAutoRange()
            self.data_plot.setData(timestamp, plot_quad)
            if (requested_quad == 2) and rdown_data.isFitted():
                fit_data = rdown_data.get_fitted_data()
                self.fit_plot.setData(fit_data[0], fit_data[1])
            else:
                self.fit_plot.clear()
            self.dataPlotWidget.autoRange()

    def display_file_size(self, filesize):
        if self._current_savefile is not None:
            self.fileSizeDisplay.setValue(filesize)

    def set_loaded_cell_style(self, chipID):
        self.interactive_wafer.chip_collection[chipID].setDataUploaded(True)

    def set_not_loaded_cell_style(self, chipID):
        self.interactive_wafer.chip_collection[chipID].setDataUploaded(False)

    def clear_memory(self):
        active_wafer =  self.wafer_list[self.active_mode]
        active_wafer.clear_data()
        self.update_wafer_image()
        self.fit_plot.clear()
        self.data_plot.clear()

    def clear_memory_selected(self):
        active_chip, active_mode = self.active_chip, self.active_mode
        #if self.chipandmode_areLoaded(active_chip, active_mode):
        #    self.loaded_data[active_chip].pop(active_mode)
        #    self.interactive_wafer.chip_collection[active_chip].setDataUploaded(False)
        self.wafer_list[active_mode].clear_chip(active_chip)
        self.update_wafer_image()
        self.fit_plot.clear()
        self.data_plot.clear()


    def chipandmode_areLoaded(self, chip, mode):
        isloaded = chip in self.wafer_list[mode].get_loaded_chips()
        return isloaded

    def chunkify_all_chip_ringdowns(self):
        if self.active_chip == '':
            print("No chip selected.")
            return

        if self.chipandmode_areLoaded(self.active_chip, self.active_mode):
            ringdowndata = self.wafer_list[self.active_mode].get_ringdowns(self.active_chip)
            selected_ringdown_idx = 0
            reference_demod = int(self.referenceDemodComboBox.currentText()) - 1
            while not ringdowndata.ringdown(0).isChunkified():
                ringdowndata.chunkify_ringdown(selected_ringdown_idx, reference_demod)

            self.update_spinbox()
            self.refresh_plot()

    def chunkify_data(self):
        action_type = self.actionRadioButtons.checkedId()
        """
        Value = 0 -> selected ringdown
        Value = 1 -> all ringdowns of chip
        Value = 2 -> all ringdowns of wafer for a mode
        """
        reference_demod = int(self.referenceDemodComboBox.currentText()) - 1
        current_wafer = self.wafer_list[self.active_mode]

        if action_type == 0 or action_type == 1:
            if self.active_chip == '':
                print("No chip selected.")
                return
            ringdowndata = current_wafer.get_ringdowns(self.active_chip)

            if action_type == 0:
                ringdown_idx = self.ringdownSpinBox.value() - 1
                ringdowndata.chunkify_ringdown(ringdown_idx, reference_demod)
            elif action_type == 1:
                ringdown_idx = 0
                while not ringdowndata.ringdown(0).isChunkified():
                    ringdowndata.chunkify_ringdown(ringdown_idx, reference_demod)
        elif action_type == 2:
            for loaded_chip in current_wafer.get_loaded_chips():
                ringdowndata = current_wafer.get_ringdowns(loaded_chip)
                ringdown_idx = 0
                while not ringdowndata.ringdown(0).isChunkified():
                    ringdowndata.chunkify_ringdown(ringdown_idx, reference_demod)

        self.update_spinbox()
        self.refresh_plot()

    def fit_data(self):
        action_type = self.actionRadioButtons.checkedId()
        """
        Value = 0 -> selected ringdown
        Value = 1 -> all ringdowns of chip
        Value = 2 -> all ringdowns of wafer for a mode
        """
        signal_demod = int(self.fitDemodComboBox.currentText()) - 1
        current_wafer = self.wafer_list[self.active_mode]
        if action_type == 0 or action_type == 1:
            if self.active_chip == '':
                print("No chip selected.")
                return
            ringdowndata = current_wafer.get_ringdowns(self.active_chip)

            if action_type == 0:
                current_xrange, _ = self.dataPlotWidget.viewRange()
                ringdown_idx = self.ringdownSpinBox.value() - 1
                fit_successful, fail_string = ringdowndata.fit_ringdown(ringdown_idx,signal_demod,
                                                                        timerange = current_xrange)
            elif action_type == 1:
                for ringdown_idx in range(ringdowndata.get_ringdown_num()):
                    single_success, fail_string = ringdowndata.fit_ringdown(ringdown_idx, signal_demod)
            resfreq, Q = ringdowndata.calculate_Qs(signal_demod)
            self.add_freq_and_Q(self.active_chip, resfreq, Q)
        elif action_type == 2:
            for loaded_chip in current_wafer.get_loaded_chips():
                ringdowndata = current_wafer.get_ringdowns(loaded_chip)
                for ringdown_idx in range(ringdowndata.get_ringdown_num()):
                    single_success, fail_string = ringdowndata.fit_ringdown(ringdown_idx, signal_demod)
                    if not single_success:
                        print(fail_string, f"Occured at chip {loaded_chip}")
                resfreq, Q = ringdowndata.calculate_Qs(signal_demod)
                self.add_freq_and_Q(loaded_chip, resfreq, Q)


        self.refresh_plot()

    def chunkify_wafer(self):
        for loaded_chip in self.wafer_list[self.active_mode].get_loaded_chips():
            ringdown_data = self.wafer_list[self.active_mode].get_ringdowns(loaded_chip)
            selected_ringdown_idx = 0
            reference_demod = int(self.referenceDemodComboBox.currentText()) - 1
            while not ringdown_data.ringdown(0).isChunkified():
                ringdown_data.chunkify_ringdown(selected_ringdown_idx, reference_demod)

        self.update_spinbox()
        self.refresh_plot()

    def add_freq_and_Q(self, chipID, frequency, Q):
        chip = self.interactive_wafer.chip_collection[chipID]
        chip.setText("f<sub>0</sub> = {:.3f} MHz".format(frequency/1e6))
        chip.append("Q = {:.3f} x 10<sup>6</sup>".format(Q/1e6))

    def clear_chip_text(self, chipID):
        chip = self.interactive_wafer.chip_collection[chipID]
        chip.setText("")

    def set_chip_info(self, chipID):
        wafer = self.wafer_list[self.active_mode]
        if chipID in wafer.get_loaded_chips():
            chip = wafer.get_ringdowns(chipID)
            if chip.hasQs():
                freq, Q = chip.getQs()
                self.add_freq_and_Q(chipID, freq, Q)
            else:
                self.clear_chip_text(chipID)
        else:
            self.clear_chip_text(chipID)

    def set_linlogscale(self):
        if self.linlogRadioButtons.checkedId() == 0:
            self.dataPlotWidget.setLogMode(y=False)
        else:
            self.dataPlotWidget.setLogMode(y=True)

    def abort_window(self):
        sys.exit()

    def export_data(self):
        wafer = self.wafer_list[self.active_mode]

        data_list = []
        for chipID in wafer.get_available_chips():
            if chipID in wafer.get_loaded_chips():
                chip = wafer.get_ringdowns(chipID)
                if chip.hasQs():
                    freq, Q = chip.getQs()
                    data_list.append([chipID, freq, Q, None])

        result_dir = self.wafer_directory / self.wafer_name / 'results' / f'mode{self.active_mode+1}'
        result_dir.mkdir(parents=True, exist_ok=True)

        create_wafer(result_dir / 'wafer_image.png', cells = (self.rows, self.cols), chip_data=data_list,
                     pad_letter=0.01)

        sortbyfirstfunc = itemgetter(0)
        sorted_list = sorted(data_list, key = sortbyfirstfunc)
        with open(result_dir / 'result_data.txt', 'w') as file:
            header = "%chipID\tFrequency (MHz)\tQ\tAdditional info\n"
            file.write(header)
            for line in sorted_list:
                line[1] /= 1e6
                line[2] /= 1e6
                file.write("{}\t{:.3f}\t{:.1f}\t{}\n".format(*line))

if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = WaferAnalyzer()
    sys.exit(app.exec_())
    # sys.exit()