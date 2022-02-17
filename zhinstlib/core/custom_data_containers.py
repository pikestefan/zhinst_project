import numpy as np

class LockinData(object):
    def __init__(self):
        self._demods = dict()

    def create_demod(self, demod, time_axis, x_quad, y_quad, frequency):
        data_container = DemodulatorDataContainer(time_axis=time_axis, x_quad=x_quad, y_quad=y_quad,
                                                  frequency=frequency)
        data_container.set_circular_coords()
        self._demods[demod] = data_container

    def get_demods(self):
        return np.array(self._demods.keys())

    def demod(self, demod):
        return self._demods[demod]



class DemodulatorDataContainer(object):
    def __init__(self, time_axis = None, x_quad = None, y_quad = None, frequency = None):
        self.x_quad = x_quad
        self.y_quad = y_quad
        self.frequency = frequency
        self.time_axis = time_axis

        self.r, self.phase = None, None

    def set_circular_coords(self, x_quad=None, y_quad=None):
        if x_quad is not None and y_quad is not None:
            complex_amp = x_quad + 1j*y_quad
        else:
            complex_amp = self.x_quad + 1j*self.y_quad
        r = np.abs(complex_amp)
        phase = np.angle(complex_amp)
        self.r, self.phase = r, phase

