import zhinst.ziPython as zi
import sys
import numpy as np
from zhinstlib.helpers.helper_funcs import get_device_props
import time
from math import ceil


class ziVirtualDevice(zi.ziDAQServer):

    def __init__(self, dev_name='', *args, **kwargs):
        super(ziVirtualDevice, self).__init__(*args, **kwargs)
        self.dev_name = dev_name
        self.__baseaddress = f'/{dev_name}'
        self._demod_num = self.get_available_demods()
        self.demod_properties = dict().fromkeys([demod for demod in range(self._demod_num)])
        self.clockbase = self.getInt(self.__baseaddress + '/clockbase')
        self.daqmodules = dict()

        for key in self.demod_properties.keys():
            self.demod_properties[key] = self.get_demod_settings(key)

        self._check_addons_onstartup()

    def _check_addons_onstartup(self):
        self._haspids = False
        self._hasmods = False

        nodes = self.get_device_nodes()

        if 'PIDS' in nodes:
            self._haspids = True
        if 'MODS' in nodes:
            self._hasmods = True

    def get_device_nodes(self):
        nodes = self.listNodes(self.__baseaddress)

        node_names = [node.split('/')[-1] for node in nodes]

        return node_names

    def poll_demod_stream(self, demod=None, duration=1, return_amp=False, timeout_ms=100, *args, **kwargs):
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
        cmd = self.__baseaddress + f'/demods/{demod}/sample'
        self.subscribe(cmd)
        self.flush()
        data = self.poll(duration, flat=True, timeout_ms=timeout_ms, *args, **kwargs)
        self.unsubscribe('*')

        assert data, "poll() returned an empty dictionary."
        assert cmd in data, "The data has no keys"

        if return_amp:
            return np.abs(data[cmd]['x'] + 1j*data[cmd]['y'])
        else:
            return data[cmd]

    def set_pid_enabled(self, pid_num=0, enabled=False):
        if self._haspids:
            cmd = self.__baseaddress + f'/pids/{pid_num}/enable'
            self.setInt(cmd, int(enabled))
        else:
            raise(Exception('Device has no PIDs'))

    def set_subscribe_daq(self, demods=None, signal_list=None, read_duration=1., burst_duration=1.,
                          module_name=None, daq_type=0, interp_method=2, save_files = False,
                          saving_dir = None, saving_fname=None, saving_fmt=4, saving_onread = False):
        """
        Method that creates a daq module, adding it to the dictionary of the class daq modules. This method also sets
        the daq module settings. Returns the name of the module as specified in the daq modules dictionary, and a
        dictionary with the subscribed signals as keys. The dictionary items are empty lists.

        :param demod: int or list, the demodulator numbers.
        :param signal_list: str or list of str, the signals to subscribe to.
        :param read_duration: float, the total measurement duration in seconds.
        :param burst_duration: float, the burst duration in seconds.
        :param module_name: str, the daq module name. If not assigned a default is created.
        :param daq_type: int, the type of data acquisition, as specified in the LabOne documentation. Default is 0
        (continuous acquisition).
        :param interp_method: int, the interpolation method, as specified in the LabOne documentation. Default is 2
        (linear interpolation).
        :return: str: the module name.
        list: the list of paths to which the module is subscribed.
        """
        if not hasattr(demods, '__iter__'):
            demods = [demods]
        if isinstance(signal_list, str):
            signal_list = [signal_list]
        if module_name is None:
            module_name = f'daq{len(self.daqmodules)}'

        demod_paths = [self.__baseaddress + f'/demods/{demod}/sample' for demod in demods]
        sampling_rate = max([self.demod_properties[demod]['rate'] for demod in demods])

        cmd_list = []
        for demod in demod_paths:
            for sig in signal_list:
                cmd_list.append(demod + f'.{sig}')

        flags = zi.ziListEnum.recursive | zi.ziListEnum.absolute | zi.ziListEnum.streamingonly
        streaming_nodes = self.listNodes(self.__baseaddress, flags)

        daq_module = self.dataAcquisitionModule()
        for demod_number, demod_path in zip(demods, demod_paths):
            if demod_path.upper() not in streaming_nodes:
                print(f'Device {self.dev_name} does not have the requested demods.')
                raise Exception("Demodulator streaming nodes unavailable.")

        num_cols = int(ceil(sampling_rate * burst_duration))
        num_bursts = int(ceil(read_duration/burst_duration))

        daq_module.set('device', self.dev_name)
        daq_module.set('type', daq_type)
        daq_module.set('grid/mode', interp_method)
        daq_module.set('count', num_bursts)
        daq_module.set('duration', burst_duration)
        daq_module.set('grid/cols', num_cols)

        if save_files:
            if saving_dir is not None:
                daq_module.set('save/directory', saving_dir)
            if saving_fname is None:
                saving_fname = 'stream'
            daq_module.set('save/filename', saving_fname)
            daq_module.set('save/fileformat', saving_fmt)
            daq_module.set('save/saveonread', saving_onread)

        for sig_path in cmd_list:
            print('Subscribing to', sig_path)
            daq_module.subscribe(sig_path)

        self.daqmodules[module_name] = daq_module

        return module_name, cmd_list

    def _read_data_stream(self, daq_module=None, data_dictionary=None, signal_paths=None, save_to_dictionary = True):
        """
        Read a data stream. Be aware that this function returns only the last burst of the data stream.

        :param daq_module: dataAcquisitionModule class, a data acquisition module.
        :param data_dictionary: a dictionary to which values are appended.
        :param signal_paths: list of str, the list of signal paths to which the daq module is subscribed.
        :return: dict, the updated data_dictionary
        """
        data_read = daq_module.read(True)
        if save_to_dictionary:
            returned_sig_paths = [signal_path.lower() for signal_path in data_read.keys()]
            for signal_path in signal_paths:
                if signal_path.lower() in returned_sig_paths:
                    for ii, signal_burst in enumerate(data_read[signal_path.lower()]):
                        time_ax = signal_burst["timestamp"][0, :] / self.clockbase
                        value = signal_burst["value"][0, :]
                        data_dictionary[signal_path].append([time_ax, value])

        return data_dictionary

    def read_daq_module(self, daq_module_name=None, signal_paths=None, timeout=None, remove_atfinish=False,
                        save_to_dictionary = True,
                        save_on_file = False):
        """
        Read a daq module contained in the class dictionary daqmodules. At the end of the read, remove the module from
        the dictionary. Remember to execute the daq module (execute_daqmodule method) before reading!

        :param daq_module_name: str, the daq module name.
        :param signal_paths: list, a list of the paths to be read.
        :param timeout: float, the timeout time in seconds. If not given the default is 1.5 * burst duration *
         burst number.
        :param remove_atfinish, bool, if True the daq module is removed from the class dictionary.
        :return: dict, the updated data dictionary.
        """
        data_dict = dict.fromkeys(signal_paths)
        for key in data_dict:
            data_dict[key] = []

        if daq_module_name not in self.daqmodules:
            print("The daq_module has not been properly set and subscribed.")
            raise Exception("Please call set and subscribe the daq first.")

        daq_module = self.daqmodules[daq_module_name]
        if timeout is None:
            timeout = 1.5 * daq_module.getDouble('count')*daq_module.getDouble('duration')

        if save_on_file:
            daq_module.set('save/save', 1)
        tstart = time.time()
        while not daq_module.finished():
            if time.time() - tstart > timeout:
                raise Exception(f"Timeout occured after {timeout} seconds. Are streaming nodes enabled?"
                                "Has a valid signal been specified?")
            data_dict = self._read_data_stream(daq_module, data_dict, signal_paths, save_to_dictionary)
        data_dict = self._read_data_stream(daq_module, data_dict, signal_paths, save_to_dictionary)

        if save_on_file:
            tstart = time.time()
            while daq_module.getInt('save/save') != 0:
                time.sleep(0.1)
                if time.time()-tstart > timeout:
                    raise Exception(f"Timeout after {timeout} second before data save completed.")

        if remove_atfinish:
            self.daqmodules.pop(daq_module_name)
        return data_dict

    def execute_daqmodule(self, daq_module_name=None):
        if daq_module_name not in self.daqmodules.keys():
            raise Exception("The module has not been set and added to the daqmodules yet.")
        self.daqmodules[daq_module_name].execute()

    def set_aux_offset(self, aux=0, offset=0):
        cmd = self.__baseaddress + f'/auxouts/{aux}/offset'
        self.setDouble(cmd, offset)

    def set_demod_harmonic(self, demod=None, harmonic=0):
        cmd = self.__baseaddress + f'/demods/{demod}/harmonic'
        self.setInt(cmd, harmonic)

    def set_demod_oscillator(self, demod=None, oscillator=0):
        cmd = self.__baseaddress + f'/demods/{demod}/oscselect'
        self.setInt(cmd, oscillator)

    def set_demod_output(self, demod=None, on_state=False, column=0):
        cmd = self.__baseaddress + f'/sigouts/{column}/enables/{demod}'
        self.setInt(cmd, int(on_state))

    def set_mod_phase(self, mod_choice='carrier', phase=0, which_mod=0):
        """
        When the MOD module is present
        :param mod_choice: either carrier, sideband0, sideband1
        :param which_mod: either 0 or 1, corresponding to MOD1, MOD2
        :return:
        """
        if self._hasmods:
            if not mod_choice.isalpha():
                signal_choice = f'sidebands/{mod_choice[-1]}'
            else:
                signal_choice = 'carrier'
            cmd = self.__baseaddress + f'/mods/{which_mod}/{signal_choice}/phaseshift'
            self.setDouble(cmd, phase)
        else:
            raise(Exception('Device has no MOD addon.'))

    def set_oscillator_freq(self, oscillator=None, frequency=None):
        cmd = self.__baseaddress + f'/oscs/{oscillator}/freq'
        self.setDouble(cmd, frequency)

    def set_output_range(self, output_channel=None, max_voltage=1):
        cmd = self.__baseaddress + f'/sigouts/{output_channel}/range'
        self.setDouble(cmd, max_voltage)

        actual_range = self.get_output_range(output_channel)
        if actual_range != max_voltage:
            print(f"Required voltage not available. Set max range to {actual_range}V instead.")

    def set_output_state(self, output_channel=None, on_state=False):
        cmd = self.__baseaddress + f'/sigouts/{output_channel}/on'
        self.setInt(cmd, int(on_state))

    def set_output_volt(self, demod=None, voltage=0, column=0):
        cmd = self.__baseaddress + f'/sigouts/{column}/amplitudes/{demod}'
        multiplier = self.get_output_range(column)
        if voltage > multiplier:
            raise Warning("The required voltage exceeds the max output range. Clipping to the maximum.")
        self.setDouble(cmd, voltage/multiplier)

    def set_demod_phase(self, demod=None, phase = 0):
        cmd = self.__baseaddress + f'/demods/{demod}/phaseshift'
        self.setDouble(cmd, phase)

    def get_available_demods(self):
        return len(self.listNodes(self.__baseaddress + '/demods'))

    def get_aux_offset(self, aux=0):
        cmd = self.__baseaddress + f'/auxouts/{aux}/offset'
        offset = self.getDouble(cmd)
        return offset

    def get_demod_harmonic(self, demod=None):
        cmd = self.__baseaddress + f'/demods/{demod}/harmonic'
        return self.getInt(cmd)

    def get_demod_oscillator(self, demod=None):
        cmd = self.__baseaddress + f'/demods/{demod}/oscselect'
        return self.getInt(cmd)

    def get_demod_output(self, demod=None, column=0):
        cmd = self.__baseaddress + f'/sigouts/{column}/enables/{demod}'
        return bool(self.getInt(cmd))

    def get_demod_settings(self, demod=None):
        props = self.listNodes(self.__baseaddress + f'/demods/{demod}', settingsonly=True)
        prop_dictionary = dict()
        for prop in props:
            value = self.getDouble(prop)
            key_name = prop.lower().split('/')[-1]
            prop_dictionary[key_name] = value
        return prop_dictionary

    def get_oscillator_freq(self, oscillator=None):
        cmd = self.__baseaddress + f'/oscs/{oscillator}/freq'
        return self.getDouble(cmd)

    def get_output_range(self, output_channel=None):
        cmd = self.__baseaddress + f'/sigouts/{output_channel}/range'
        return self.getDouble(cmd)

    def get_output_state(self, output_channel=None):
        cmd = self.__baseaddress + f'/sigouts/{output_channel}/on'
        return bool(self.getInt(cmd))

    def get_demod_phase(self, demod=None):
        cmd = self.__baseaddress + f'/demods/{demod}/phaseshift'
        return self.getDouble(cmd)

    def optimize_freq(self, demod=None, wait_time=None, min_delta=1e-6, stepsize=0.5, itermax=1000, gain_factor=2,
                         integration_time=0.1):
        #TODO:estimate wait_time and poll integration time from Q factor
        poll_kwargs = {'timeout_ms': 500,
                       'flags': 0}

        freq = self.get_oscillator_freq(demod)

        ii = 0
        prev_gradient = np.nan
        contrast = 2*min_delta
        gain = 1

        curr_amp = self.poll_demod_stream(demod, integration_time, return_amp=True, **poll_kwargs).mean()
        direction = 1
        while abs(contrast) > min_delta and ii < itermax:
            new_freq = freq + direction*gain*stepsize
            self.set_oscillator_freq(demod, new_freq)
            time.sleep(wait_time)
            new_amp = self.poll_demod_stream(demod, integration_time, return_amp=True, **poll_kwargs).mean()

            gradient = (new_amp - curr_amp)

            if gradient < 0:
                direction *= -1

            reduce_gain = (gradient < 0) and (prev_gradient >= 0)

            if reduce_gain:
                gain /= gain_factor

            if not reduce_gain:
                freq = new_freq
                curr_amp = new_amp
            else:
                self.set_oscillator_freq(demod, freq)
                time.sleep(wait_time)
                curr_amp = self.poll_demod_stream(demod, integration_time, return_amp=True, **poll_kwargs).mean()

            prev_gradient = gradient
            contrast = gradient / (new_amp + curr_amp)
            ii += 1

        if ii == itermax:
            print("Max. iteration number reached.")
        else:
            print("Converged")

    def sweep_freq_and_optimize(self, demod=None, settle_time = None, int_time = None,
                                coarse_range=5, fine_range=20e-3, coarse_steps=5, fine_steps=6):

        #TODO:estimate wait_time and poll integration time from Q factor
        poll_kwargs = {'timeout_ms': 500,
                       'flags': 0}

        for range in [coarse_range, fine_range]:
            freq0 = self.get_oscillator_freq(demod)
            freq_half_range = range / 2
            if range == coarse_range:
                steps = coarse_steps
            else:
                steps = fine_steps
            freq_steps = np.linspace(freq0 - freq_half_range, freq0 + freq_half_range, steps)
            measured_amps = np.zeros(freq_steps.shape)

            for ii, freq in enumerate(freq_steps):

                self.set_oscillator_freq(demod, freq)
                time.sleep(settle_time)
                curr_amp = self.poll_demod_stream(demod, int_time, return_amp=True, **poll_kwargs).max()
                measured_amps[ii] = curr_amp
            max_freq = freq_steps[np.argmax(measured_amps)]

        return max_freq


if __name__ == '__main__':

    import matplotlib.pyplot as plt

    device_id = 'dev1347'

    props = get_device_props(device_id)

    dev = ziVirtualDevice(device_id, props['serveraddress'], props['serverport'], props['apilevel'])