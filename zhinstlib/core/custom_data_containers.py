import numpy as np

class RingdownContainer(object):
    """
    A container which is essentially is a collection of lock-in data. Used to store the different ringdowns.
    """
    def __init__(self):
        self._ringdowns = []

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

class LockinData(object):
    """
    Stores the data of each single demodulator. The single demods can be easily invoked using the demod function.
    """
    def __init__(self):
        self._demods = dict()

    def create_demod(self, demod, time_axis, x_quad, y_quad, frequency):
        data_container = DemodulatorDataContainer(time_axis=time_axis, x_quad=x_quad, y_quad=y_quad,
                                                  frequency=frequency)
        data_container.get_ampphase_quads()
        self._demods[demod] = data_container

    def get_demods(self):
        return list(self._demods.keys())

    def demod(self, demod):
        return self._demods[demod]



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

    def get_ampphase_quads(self, x_quad=None, y_quad=None):
        if x_quad is not None and y_quad is not None:
            complex_amp = x_quad + 1j*y_quad
        else:
            complex_amp = self.x_quad + 1j*self.y_quad
        r = np.abs(complex_amp)
        phase = np.angle(complex_amp)
        self.r_quad, self.phase_quad = r, phase

