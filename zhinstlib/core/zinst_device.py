from zhinst.ziPython import ziDAQServer, ziListEnum
import numpy as np
from zhinstlib.helpers.helper_funcs import get_device_props
import time
from math import ceil
from PyQt5.QtCore import QObject, pyqtSignal, pyqtSlot


class ziVirtualDevice(object):
    def __init__(self, dev_name="", auto_properties=True, *args, **kwargs):
        super(ziVirtualDevice, self).__init__()
        if auto_properties:
            device_props = get_device_props(dev_name)
            args = [
                device_props["serveraddress"],
                device_props["serverport"],
                device_props["apilevel"],
            ]

        self.ziServer = ziDAQServer(*args, **kwargs)
        self.dev_name = dev_name
        self._baseaddress = f"/{dev_name}"
        self._demod_num = self.get_available_demods()
        self.demod_properties = dict().fromkeys(
            [demod for demod in range(self._demod_num)]
        )
        self.clockbase = self.ziServer.getInt(self._baseaddress + "/clockbase")
        self.daqmodules = dict()
        self.daqmodules_sigs = dict()
        self._daqstopRequested = False

        for key in self.demod_properties.keys():
            self.demod_properties[key] = self.get_demod_settings(key)

        self._check_addons_onstartup()

    def _check_addons_onstartup(self):
        self._haspids = False
        self._hasmods = False

        nodes = self.get_device_nodes()

        if "PIDS" in nodes:
            self._haspids = True
        if "MODS" in nodes:
            self._hasmods = True

    def get_device_nodes(self):
        nodes = self.ziServer.listNodes(self._baseaddress)

        node_names = [node.split("/")[-1] for node in nodes]

        return node_names

    def request_stop(self):
        self._daqstopRequested = True

    def poll_demod_stream(
        self, demod=None, duration=1, return_amp=False, timeout_ms=100, *args, **kwargs
    ):
        """
        Function that polls a stream in a blocking fashion. By default, it can only return x and y plus additional
        specifiers. For more complex signal subscritpions, check the read_data_stream/read_daq_module methods.
        :param demod: int, the demodulator number.
        :param duration: float, the polling duration in seconds.
        :param return_amp: bool, if True, return only the modulus of X + iY.
        :param timeout_ms: float, the timeout for polling the stream.
        :param args: passed onto the poll method
        :param kwargs: passed onto the poll method
        :return:
        """
        cmd = self._baseaddress + f"/demods/{demod}/sample"
        self.ziServer.subscribe(cmd)
        self.ziServer.flush()
        data = self.ziServer.poll(
            duration, flat=True, timeout_ms=timeout_ms, *args, **kwargs
        )
        self.ziServer.unsubscribe("*")

        assert data, "poll() returned an empty dictionary."
        assert cmd in data, "The data has no keys"

        if return_amp:
            return np.abs(data[cmd]["x"] + 1j * data[cmd]["y"])
        else:
            return data[cmd]

    def set_pid_enabled(self, pid_num=0, enabled=False):
        if self._haspids:
            cmd = self._baseaddress + f"/pids/{pid_num}/enable"
            self.ziServer.setInt(cmd, int(enabled))
        else:
            raise (Exception("Device has no PIDs"))

    def set_subscribe_daq(
        self,
        demod_dictionary=dict(),
        read_duration=None,
        burst_duration=None,
        module_name=None,
        daq_type="continous",
        interp_method="linear",
        autosaving_file_path=None,
        autosave_file_fmt="hdf5",
        triggernode="",
        **kwargs,
    ):
        """
        Method that creates a daq module, adding it to the dictionary of the class daq modules. This method also sets
        the daq module settings. Returns the name of the module as specified in the daq modules dictionary, and a
        dictionary with the subscribed signals as keys. The dictionary items are empty lists.
        """
        filefmt_dictionary = {"matlab": 0, "csv": 1, "xsm": 3, "hdf5": 4}
        daq_type_dict = {
            "continous": 0,
            "edge": 1,
            "pulse": 3,
            "tracking": 4,
            "digital": 2,
            "hardware": 6,
            "pulse counter": 8,
        }
        interp_method_dict = {"nearest": 1, "linear": 2, None: 4}

        cmd_string = self._baseaddress + "/demods/{:d}/sample.{}"

        if daq_type not in daq_type_dict:
            raise ValueError(
                f"The daq type {daq_type} is not available. "
                f"Allowed values are {list(daq_type_dict.keys())}"
            )
        else:
            daq_type = daq_type_dict[daq_type]
        if interp_method not in interp_method_dict:
            raise ValueError(
                f"The interpolation method type {interp_method} is not available. "
                f"Allowed values are {list(interp_method_dict.keys())}"
            )
        else:
            interp_method = interp_method_dict[interp_method]
        if autosave_file_fmt in filefmt_dictionary:
            filefmt_idx = filefmt_dictionary[autosave_file_fmt]
        else:
            raise ValueError(
                "The file format is not valid. Valid formats are:  {}".format(
                    list(filefmt_dictionary.keys())
                )
            )

        if module_name is None:
            module_name = f"daq{len(self.daqmodules)}"

        cmd_list = []
        for demod, signals in demod_dictionary.items():
            for sig in signals:
                cmd_list.append(cmd_string.format(demod, sig))

        flags = ziListEnum.recursive | ziListEnum.absolute | ziListEnum.streamingonly
        streaming_nodes = self.ziServer.listNodes(self._baseaddress, flags)
        streaming_nodes = [stream.lower() for stream in streaming_nodes]

        daq_module = self.ziServer.dataAcquisitionModule()

        for demod in demod_dictionary:
            demod_path = self._baseaddress + f"/demods/{demod}/sample"
            if demod_path not in streaming_nodes:
                print(f'Device {self.dev_name} does not have the requested demods.')
                raise Exception("Demodulator streaming nodes unavailable.")

        if triggernode:
            daq_module.set("triggernode", self._baseaddress + f"/{triggernode}")

        if burst_duration is not None and read_duration is not None:
            sampling_rate = max(
                [self.get_sampling_rate(demod) for demod in demod_dictionary]
            )

            for demod in demod_dictionary:
                self.set_sampling_rate(demod, sampling_rate)

            num_cols = int(ceil(sampling_rate * burst_duration))
            if daq_type == 0:
                num_bursts = int(ceil(read_duration / burst_duration))
                daq_module.set("count", num_bursts)
                daq_module.set("grid/cols", num_cols)

            if interp_method != 4:
                daq_module.set(
                    "duration", burst_duration
                )  # This parameter is read-only in exact acquisition

        daq_module.set("device", self.dev_name)
        daq_module.set("type", daq_type)
        daq_module.set("grid/mode", interp_method)

        for keyword, value in kwargs.items():
            daq_module.set(keyword, value)

        if autosaving_file_path:
            saving_directory = str(autosaving_file_path.parent)
            filename = autosaving_file_path.name
            daq_module.set("save/directory", saving_directory)
            daq_module.set("save/filename", filename)
            daq_module.set("save/fileformat", filefmt_idx)
            daq_module.set("save/saveonread", True)
        else:
            daq_module.set("save/saveonread", False)

        for requested_signal in cmd_list:
            daq_module.subscribe(requested_signal)

        self.daqmodules[module_name] = daq_module
        self.daqmodules_sigs[module_name] = cmd_list

        return module_name

    def read_daq_module(self, daq_module_name, clear_after_finish=False):
        daq_module = self.daqmodules[daq_module_name]
        daq_module_signals = self.daqmodules_sigs[daq_module_name]

        read_dictionary = daq_module.read(True)  # Return as a flat dictionary

        out_dictionary = dict()
        header_dictionary = dict()
        for signal in daq_module_signals:
            if signal in read_dictionary:
                signal_values = read_dictionary.pop(signal)
                # signal = signal.replace(self._baseaddress, '')
                data = np.zeros(
                    (len(signal_values),) + signal_values[0]["timestamp"].shape
                )
                timestamp = np.copy(data)

                temp_head_dicts = [0]*len(signal_values)
                for ii, signal_value in enumerate(signal_values):
                    data[ii] = signal_value["value"]
                    timestamp[ii] = signal_value["timestamp"]/self.clockbase
                    temp_head_dicts[ii] = signal_value["header"]
            else:
                timestamp, data, temp_head_dicts = None, None, None

            out_dictionary[signal] = [timestamp, data]
            header_dictionary[signal] = temp_head_dicts

        if clear_after_finish:
            self.daqmodules.pop(daq_module_name)
            self.daqmodules_sigs.pop(daq_module_name)
        return out_dictionary, (header_dictionary, read_dictionary)

    def execute_daqmodule(self, daq_module_name=None):
        if daq_module_name not in self.daqmodules.keys():
            raise Exception(
                "The module has not been set and added to the daqmodules yet."
            )
        self.daqmodules[daq_module_name].execute()

    def stop_daqmodule(self, daq_module_name=None):
        if daq_module_name not in self.daqmodules.keys():
            raise Exception(
                "The module has not been set and added to the daqmodules yet."
            )
        self.daqmodules[daq_module_name].finish()

    def remove_daqmodule(self, daq_module_name=None):
        if daq_module_name not in self.daqmodules.keys():
            raise Exception(
                "The module has not been set and added to the daqmodules yet."
            )
        else:
            self.daqmodules.pop(daq_module_name)

    def wait_daqmodule(self, daq_module_name=None):
        if daq_module_name not in self.daqmodules.keys():
            raise Exception("The module has not been set and added to the daqmodules yet.")
        else:
            while not self.daqmodules[daq_module_name].finished():
                pass

    def get_subscribed_signals(self, daqmodule_name):
        return [
            signal.replace(self._baseaddress, "")
            for signal in self.daqmodules_sigs[daqmodule_name]
        ]

    def set_aux_offset(self, aux=0, offset=0):
        cmd = self._baseaddress + f"/auxouts/{aux}/offset"
        self.ziServer.setDouble(cmd, offset)

    def set_demod_harmonic(self, demod=None, harmonic=0):
        cmd = self._baseaddress + f"/demods/{demod}/harmonic"
        self.ziServer.setInt(cmd, harmonic)

    def set_demod_oscillator(self, demod=None, oscillator=0):
        cmd = self._baseaddress + f"/demods/{demod}/oscselect"
        self.ziServer.setInt(cmd, oscillator)

    def set_demod_output(self, demod=None, on_state=False, column=0):
        cmd = self._baseaddress + f"/sigouts/{column}/enables/{demod}"
        self.ziServer.setInt(cmd, int(on_state))

    def set_mod_phase(self, mod_choice="carrier", phase=0, which_mod=0):
        """
        When the MOD module is present
        :param mod_choice: either carrier, sideband0, sideband1
        :param which_mod: either 0 or 1, corresponding to MOD1, MOD2
        :return:
        """
        if self._hasmods:
            if not mod_choice.isalpha():
                signal_choice = f"sidebands/{mod_choice[-1]}"
            else:
                signal_choice = "carrier"
            cmd = self._baseaddress + f"/mods/{which_mod}/{signal_choice}/phaseshift"
            self.ziServer.setDouble(cmd, phase)
        else:
            raise (Exception("Device has no MOD addon."))

    def set_oscillator_freq(self, oscillator=None, frequency=None):
        cmd = self._baseaddress + f"/oscs/{oscillator}/freq"
        self.ziServer.setDouble(cmd, frequency)

    def set_output_range(self, output_channel=None, max_voltage=1):
        cmd = self._baseaddress + f"/sigouts/{output_channel}/range"
        self.ziServer.setDouble(cmd, max_voltage)

        actual_range = self.get_output_range(output_channel)
        if actual_range != max_voltage:
            print(
                f"Required voltage not available. Set max range to {actual_range}V instead."
            )

    def set_output_state(self, output_channel=None, on_state=False):
        cmd = self._baseaddress + f"/sigouts/{output_channel}/on"
        self.ziServer.setInt(cmd, int(on_state))

    def set_output_volt(self, demod=None, voltage=0, column=0):
        cmd = self._baseaddress + f"/sigouts/{column}/amplitudes/{demod}"
        multiplier = self.get_output_range(column)
        if voltage > multiplier:
            raise Warning(
                "The required voltage exceeds the max output range. Clipping to the maximum."
            )
        self.ziServer.setDouble(cmd, voltage / multiplier)

    def set_demod_phase(self, demod=None, phase=0):
        cmd = self._baseaddress + f"/demods/{demod}/phaseshift"
        self.ziServer.setDouble(cmd, phase)

    def set_sampling_rate(self, demod=None, sampling_rate=None):
        cmd = self._baseaddress + f"/demods/{demod}/rate"
        self.ziServer.setDouble(cmd, sampling_rate)

    def get_available_demods(self):
        return len(self.ziServer.listNodes(self._baseaddress + "/demods"))

    def get_aux_offset(self, aux=0):
        cmd = self._baseaddress + f"/auxouts/{aux}/offset"
        offset = self.ziServer.getDouble(cmd)
        return offset

    def get_demod_harmonic(self, demod=None):
        cmd = self._baseaddress + f"/demods/{demod}/harmonic"
        return self.ziServer.getInt(cmd)

    def get_demod_oscillator(self, demod=None):
        cmd = self._baseaddress + f"/demods/{demod}/oscselect"
        return self.ziServer.getInt(cmd)

    def get_demod_output(self, demod=None, column=0):
        cmd = self._baseaddress + f"/sigouts/{column}/enables/{demod}"
        return bool(self.ziServer.getInt(cmd))

    def get_demod_settings(self, demod=None):
        props = self.ziServer.listNodes(
            self._baseaddress + f"/demods/{demod}", settingsonly=True
        )
        prop_dictionary = dict()
        for prop in props:
            value = self.ziServer.getDouble(prop)
            key_name = prop.lower().split("/")[-1]
            prop_dictionary[key_name] = value
        return prop_dictionary

    def get_oscillator_freq(self, oscillator=None):
        cmd = self._baseaddress + f"/oscs/{oscillator}/freq"
        return self.ziServer.getDouble(cmd)

    def get_output_range(self, output_channel=None):
        cmd = self._baseaddress + f"/sigouts/{output_channel}/range"
        return self.ziServer.getDouble(cmd)

    def get_output_state(self, output_channel=None):
        cmd = self._baseaddress + f"/sigouts/{output_channel}/on"
        return bool(self.ziServer.getInt(cmd))

    def get_output_volt(self, demod=None, column=0):
        cmd = self._baseaddress + f"/sigouts/{column}/amplitudes/{demod}"
        multiplier = self.get_output_range(column)

        voltage = self.ziServer.getDouble(cmd)

        return voltage * multiplier

    def get_demod_phase(self, demod=None):
        cmd = self._baseaddress + f"/demods/{demod}/phaseshift"
        return self.ziServer.getDouble(cmd)

    def get_pid_enabled(self, pid_num=0):
        if self._haspids:
            cmd = self._baseaddress + f'/pids/{pid_num}/enable'
            return bool(self.ziServer.getInt(cmd))
        else:
            raise (Exception('Device has no PIDs'))

    def get_sampling_rate(self, demod=None):
        cmd = self._baseaddress + f"/demods/{demod}/rate"
        return self.ziServer.getDouble(cmd)

    def sync(self):
        self.ziServer.sync()


class PyQtziVirtualDevice(ziVirtualDevice, QObject):

    signal_stop_daq = pyqtSignal()
    signal_acquisition_completed = pyqtSignal()

    def __init__(self, dev_name="", auto_properties=True, *args, **kwargs):
        super(PyQtziVirtualDevice, self).__init__(
            dev_name=dev_name, auto_properties=auto_properties, *args, **kwargs
        )

        self.signal_stop_daq.connect(self.request_stop)
