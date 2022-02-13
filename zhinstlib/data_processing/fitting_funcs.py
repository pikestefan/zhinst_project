import numpy as np


def lorentz_func(freqs, freq0, FWHM, amp):

    return amp*(FWHM/2)**2/((FWHM/2)**2 + np.square(freqs-freq0))

def normalized_nlin_rdown(t, gamma, gamma_nlin, y0):
    return np.exp(-gamma*t/2) / np.sqrt(1 + gamma_nlin*(1-np.exp(-gamma*t))/(4*gamma)) + y0

def nlin_rdown(t, gamma, gamma_nlin, y0, A):
    return A * np.exp(-gamma*t/2) / np.sqrt(1 + A**2*gamma_nlin*(1-np.exp(-gamma*t))/(4*gamma)) + y0

def lin_rdown(t, gamma, y0, A):
    return A * np.exp(-gamma*t/2) + y0

def parametric_gain(phi_res = np.array([]), phi_par = 0, kpkT_ratio = 0):
    if isinstance(kpkT_ratio, np.ndarray):
        if not isinstance(phi_res, np.ndarray):
            phi_res = np.array([phi_res])
        if not isinstance(phi_par, np.ndarray):
            phi_par = np.array([phi_par])

        phi_res = phi_res[:, None, None]
        phi_par = phi_par[None, :, None]
        kpkT_ratio = kpkT_ratio[None, None, :]

    elif isinstance(phi_res, np.ndarray) and isinstance(phi_par, np.ndarray):
        phi_res = phi_res[:, None]
        phi_par = phi_par[None, :]

    left_numerator = np.square(np.cos(phi_res) - kpkT_ratio*np.cos(phi_res-phi_par))
    right_numerator = np.square(np.sin(phi_res) + kpkT_ratio*np.sin(phi_res-phi_par))

    den = np.square(1-np.square(kpkT_ratio))

    return np.sqrt((left_numerator + right_numerator) / den)