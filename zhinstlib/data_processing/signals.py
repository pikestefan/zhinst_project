import numpy as np
from numpy.fft import fft, fftfreq, fftshift
from scipy.optimize import curve_fit
from zhinstlib.data_processing import fitting_funcs


def power_spectrum(timetrace, signal, time_chunk=1, shift_freq = True, return_average=True):

    tstep = timetrace[1] - timetrace[0]

    chunk_len = int(round(time_chunk / tstep))

    sig_len = len(signal)
    chunks = int(sig_len // chunk_len)

    if chunks == 0:
        raise (Exception("The requested time chunk exceeds the total signal length. Decrease the time_chunk value."))

    reduced_signal = signal[:chunks * chunk_len]

    reduced_signal = reduced_signal.reshape((chunks, chunk_len))

    freq_axis = fftfreq(chunk_len, tstep)

    fouried = fft(reduced_signal, axis=1)

    pspectrum = tstep * np.square(np.abs(fouried)) / chunk_len

    if shift_freq:
        shifted = fftshift(np.row_stack((freq_axis, pspectrum)), axes=1)
        freq_axis = shifted[0, :]
        pspectrum = shifted[1:, :]

    if return_average:
        pspectrum = pspectrum.mean(axis=0)

    return freq_axis, pspectrum


def get_Q_factor(ringdown, res_freq, threshold=200e-6, *args, **kwargs):
    timetrace, decay = ringdown[:, 0], np.copy(ringdown[:, 1])
    decay /= decay.max()
    data_above_thresh = decay[decay > threshold]
    gamma_guess = (-2 * np.diff(np.log(data_above_thresh)) / (timetrace[1] - timetrace[0])).mean()

    fit_guess = [gamma_guess, 0, 0, 1]

    fit_result, _ = curve_fit(fitting_funcs.nlin_rdown, timetrace, decay, p0=fit_guess, *args, **kwargs)

    Q_factor = 2 * np.pi * res_freq / fit_result[0]
    return fit_result, Q_factor

