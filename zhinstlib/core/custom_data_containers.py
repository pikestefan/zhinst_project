import numpy as np
import h5py
from zhinstlib.data_processing.data_manip import chunkify_timetrace
from zhinstlib.data_processing.fitting_funcs import lin_rdown
from scipy.optimize import curve_fit

class WaferFitContainer(object):
    """
    A class used to store in memory the fit results for all the chips and all the modes, even when the actual data are deleted
    """
    def __init__(self):
        self._mode_dictionary = dict() #Each item will be a dictionary of chips
        self._chip_usable = dict() #Use to store if the chip has been marked as usable or not

    def set_freq_Q(self, mode_frequency, Qfactor, mode, chipID):
        if mode not in self._mode_dictionary.keys():
            self._mode_dictionary[mode] = dict()

        selected_mode = self._mode_dictionary[mode]
        selected_mode[chipID] = [mode_frequency, Qfactor]

    def mode(self, mode_idx):
        return self._mode_dictionary[mode]

    def hasQs(self, mode_idx, chipID):
        if mode_idx in self._mode_dictionary and chipID in self._mode_dictionary[mode_idx]:
            chip = self._mode_dictionary[mode_idx][chipID]
            hasqs = (chip[0] is not None) and (chip[1]) is not None
        else:
            hasqs = False
        return hasqs

    def getQs(self, mode_idx, chipID):
        return self._mode_dictionary[mode_idx][chipID]

    def get_chips_with_Qs(self, mode_idx):
        return self._mode_dictionary[mode_idx].keys()

    def set_chip_usable(self, value, mode, chipID):
        if mode not in self._chip_usable.keys():
            self._chip_usable[mode] = dict()
        self._chip_usable[mode][chipID] = value

    def isUsable(self, mode_idx, chipID):
        if mode_idx in self._chip_usable and chipID in self._chip_usable[mode_idx]:
            return self._chip_usable[mode_idx][chipID]
        else:
            return True
"""
Here there are some nested classes:
- WaferContainer: a collection of chips for a given mechanical mode. Each chip is a RingdownContainer.
- RingdownContainer: a collection of ringdowns. Each ringdown is a collection of LockinData.
- LockinData: contains the data of all demodulators for a given timetrace. Each demodulator is represented by a DemodulatorDataContainer
- DemodulatorDataContainer: the most basic class. Contains the time axis, x, y, ampltiude and phase quadratures. The 
                            fit results are stored in this last data container.
"""

class WaferDataContainer(object):
    def __init__(self, mode):
        super(WaferDataContainer, self).__init__()
        self.mode = mode
        self._chip_ringdowns = dict()
        self._available_chips = []

    def add_ringdowns(self, chipID, ringdown_container):
        if not isinstance(ringdown_container, RingdownDataContainer):
            print("The ringdowns passed must by an instance of RingdownContainer")
            return

        self._chip_ringdowns[chipID] = ringdown_container

    def get_ringdowns(self, chipID):
        return self._chip_ringdowns[chipID]

    def add_available_chip(self, chipID):
        """
        Used in wafer loading mode. Append the chip name to the avaiable_chips list.
        Used to quickly check which chips can be interacted with.
        """
        self._available_chips.append(chipID)

    def get_available_chips(self):
        return self._available_chips

    def get_loaded_chips(self):
        return self._chip_ringdowns.keys()

    def is_empty(self):
        isempty = True if len(self._chip_ringdowns) == 0 else True
        return

    def clear_data(self):
        self._chip_ringdowns = dict()

    def clear_chip(self, chipID):
        self._chip_ringdowns.pop(chipID)


class RingdownDataContainer(object):
    """
    A container which is essentially is a collection of lock-in data. Used to store the different ringdowns.
    """

    def __init__(self):
        self._ringdowns = []
        self._res_freq_mean = None
        self._Q_mean = None

    def add_ringdown_sequence(self, lockincontainer):
        self._ringdowns.append(lockincontainer)

    def get_ringdown_num(self):
        return len(self._ringdowns)

    def get_ringdown_demods(self, ringdown = 0):
        """
        Returns the demodulators for a given ringdown sequence.
        """
        return self._ringdowns[ringdown].get_demods()

    def ringdown(self, ringdown = 0):
        """
        Returns the LockinData container for a given ringdown
        """
        return self._ringdowns[ringdown]

    def load_ringdown(self, filepath, h5file_demodpath):
        """
        :param filepath: the path of the h5 file
        :param h5file_demodpath: the path to the demodulators in the h5 dictionary
        """
        ringdown_li_data = LockinData()

        with h5py.File(filepath, 'r') as file:
            demod_templist = [int(key) for key in file[h5file_demodpath].keys()]
            for demod in demod_templist:
                timestamp = file[h5file_demodpath + f"/{demod}/sample.frequency/timestamp"][:]
                timestamp = (timestamp - timestamp[0]) / 210e6

                frequency = file[h5file_demodpath + f"/{demod}/sample.frequency/value"][:].mean()
                x_quad = file[h5file_demodpath + f"/{demod}/sample.x/value"][:]
                y_quad = file[h5file_demodpath + f"/{demod}/sample.y/value"][:]

                ringdown_li_data.create_demod(demod, time_axis=timestamp,
                                              x_quad=x_quad, y_quad=y_quad,
                                              frequency=frequency)

        self.add_ringdown_sequence(ringdown_li_data)

    def chunkify_ringdown(self, ringdown_idx, reference_demod):
        """
        :param ringdown_idx: Index of the ringdown in python indexing
        """
        if not self._ringdowns[ringdown_idx].isChunkified():
            ringdown = self._ringdowns.pop(ringdown_idx)
            chunked_ringdown_list = ringdown.chunkify_demods(reference_demod)
            self._ringdowns = self._ringdowns + chunked_ringdown_list

    def fit_ringdown(self, ringdown_idx, signal_demod, timerange = None):
        success_flag = self._ringdowns[ringdown_idx].fit_demod_decay(signal_demod, timerange=timerange)

        successful = True if success_flag == 0 else False
        fail_string = ''
        if not successful:
            fail_string = f"Fit failed at ringdown {ringdown_idx}."
        return successful, fail_string

    def calculate_Qs(self, signal_demod):
        """
        Here I assume that there is only one demodulator that carries the decays
        """
        Q_array = np.zeros((len(self._ringdowns), 2))
        for ii, ringdown in enumerate(self._ringdowns):
            decay_demod = ringdown.demod(signal_demod)
            if decay_demod.isFitted():
                Q_array[ii] = [decay_demod.frequency, 2*np.pi*decay_demod.frequency / decay_demod.get_mechmode_gamma()]

        Q_array = Q_array[Q_array[:,0]!=0, :].mean(axis = 0)

        self._res_freq_mean, self._Q_mean = Q_array
        return self._res_freq_mean, self._Q_mean

    def hasQs(self):
        hasqs = (self._res_freq_mean is not None) and (self._Q_mean is not None)
        return hasqs

    def getQs(self):
        return self._res_freq_mean, self._Q_mean



class LockinData(object):
    """
    Stores the data of each single demodulator. The single demods can be easily invoked using the demod function.
    """
    def __init__(self, chunkified = False):
        self._demods = dict()
        self._chunkified = chunkified

    def create_demod(self, demod, time_axis, x_quad, y_quad, frequency):
        data_container = DemodulatorDataContainer(time_axis=time_axis, x_quad=x_quad, y_quad=y_quad,
                                                  frequency=frequency)
        data_container.get_ampphase_quads()
        self._demods[demod] = data_container

    def get_demods(self):
        return list(self._demods.keys())

    def demod(self, demod):
        return self._demods[demod]

    def pop(self, demod):
        self._demods.pop(demod)

    def isChunkified(self):
        return self._chunkified

    def chunkify_demods(self, reference_demod):
        """
        Chunkify the signal using the reference demodulator. Delete the reference signal afterwards.
        :param ringdown_idx: the ringdown index, in python indexing
        :param signal_demod: the index of the signal demodulator, in python indexing
        :param reference_demod: the index of the reference demodulator, in python indexing
        :return list of the new LockinData
        """
        reference_signal = self._demods[reference_demod].r_quad
        chunk_num = len(chunkify_timetrace(reference_signal, reference_signal)) #Trick to know the number of chunks in advance
        self.pop(reference_demod) #Remove the demod from the demod dictionary.

        #Now chunk up the rest of the demods. First create a list of new empty Lockin containers.
        lockin_list = [LockinData(chunkified=True) for _ in range(chunk_num)]
        for demod_num, data in self._demods.items():

            #Stack up the data to chunk them up
            data_stack = np.vstack((data.time_axis,
                                    data.x_quad,
                                    data.y_quad))

            chunked_signals = chunkify_timetrace(data_stack, reference_signal)

            for chunk_num, data_chunk in enumerate(chunked_signals):
                data_chunk[0,:] -= data_chunk[0,0] #Set the beginning of time to be zero
                lockin_list[chunk_num].create_demod(demod_num, *data_chunk, data.frequency)

        return lockin_list

    def fit_demod_decay(self, demod_idx, timerange = None):
        signal_demod = self._demods[demod_idx]
        success_flag = 0
        if not signal_demod.isFitted():
            if (timerange is not None) and (len(timerange) == 2):
                timeaxmask = np.logical_and( signal_demod.time_axis >= timerange[0],
                                             signal_demod.time_axis <= timerange[1])
                x_ax_fit = signal_demod.time_axis[timeaxmask]
                start_time = x_ax_fit[0]
                y_ax_fit = signal_demod.r_quad[timeaxmask]
            else:
                start_time = 0
                x_ax_fit = signal_demod.time_axis
                y_ax_fit = signal_demod.r_quad

            x_ax_fit -= start_time
            #TODO: for now juse use a linear ringdown. In the future, it should be a user choice.

            #Use the first half a second of decay to guess the gamma
            gamma_guess = abs( (np.diff( y_ax_fit[x_ax_fit <= 0.5]) / np.diff( x_ax_fit[x_ax_fit <= 0.5] )).mean() )
            amp_guess = y_ax_fit[0]
            y0_guess = 0

            try:
                fitfunc = lin_rdown # Here in case it is going to be replaced by some user-defined function
                optimal_pars, cov_mat = curve_fit(fitfunc, x_ax_fit, y_ax_fit, p0 = [gamma_guess, y0_guess, amp_guess],
                                                  maxfev=10000, gtol = 1e-12)

                signal_demod.set_mechmode_gamma(optimal_pars[0])

                signal_demod.set_fit_info( [optimal_pars, start_time, x_ax_fit[-1], fitfunc] )

            except:
                success_flag = -1

        return success_flag

class DemodulatorDataContainer(object):
    """
    The most core container. It stores the quadratures, frequency and timestamp of a demodulator.
    """
    def __init__(self, time_axis = None, x_quad = None, y_quad = None, frequency = None):
        self.x_quad = x_quad
        self.y_quad = y_quad
        self.frequency = frequency
        self.time_axis = time_axis

        self.r_quad, self.phase_quad = None, None

        self._mechmode_gamma = None

        #should be a list ordered as: [optimal fit pars, start time, stop time, fit function]
        self._fit_info = None

    def get_ampphase_quads(self, x_quad=None, y_quad=None):
        if x_quad is not None and y_quad is not None:
            complex_amp = x_quad + 1j*y_quad
        else:
            complex_amp = self.x_quad + 1j*self.y_quad
        r = np.abs(complex_amp)
        phase = np.angle(complex_amp)
        self.r_quad, self.phase_quad = r, phase

    def set_mechmode_gamma(self, gamma):
        self._mechmode_gamma = gamma

    def get_mechmode_gamma(self):
        return self._mechmode_gamma

    def isFitted(self):
        isfitted = self._fit_info is not None
        return isfitted

    def get_fitted_data(self):
        opt_pars, start, stop, fitfunc = self._fit_info
        x_ax = np.linspace(0, stop, 1000) # Hardcoded value to ensure the looks of a smooth fit function in the plot.
        y_ax = fitfunc(x_ax, *opt_pars)
        return np.vstack((x_ax+start, y_ax))

    def set_fit_info(self, fit_info):
        self._fit_info = fit_info





