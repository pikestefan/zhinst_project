import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle, Circle
from zhinstlib.data_processing.fitting_funcs import nlin_rdown
from inspect import signature
from math import sqrt


def create_wafer(savedir, cells=(5, 5), chip_data=None, extra_space=0, pad_letter=0, bad_thresh=1e6, good_thresh=10e6,
                 figsize=(15.5, 15.5)):
    """
    :param tuple cells: number of cells in the wafer. The four corners are not printed out.
    :param list chip_data: the data for each chip. Each element of the list should be arranged as [chip name, frequency, Q, additional info].
                           Additional info is a string to be used to specify additional info, if needed.
    :param extra_space:
    :param pad_letter:
    :param bad_thresh:
    :param good_thresh:
    :param figsize:
    :return:
    """
    chip_info = [[None for jj in range(cells[1])] for ii in range(cells[0])]

    for data in chip_data:
        name, freq, Q, extra_info = data
        col_letter = ord((name[0] if name[0].isalpha() else name[1]).upper()) - ord('A')
        row_number = int(name[0] if name[0].isdigit() else name[1]) - 1
        chip_info[row_number][col_letter] = [freq, Q, extra_info]

    fig = plt.figure(figsize=figsize)
    ax = fig.gca()
    plt.axis('off')
    ax.set_xlim(-0.5, 0.5)
    ax.set_ylim(-0.5, 0.5)

    rad = 0.5

    sq_edge = rad * (1 - extra_space) * sqrt(2)

    single_cell_side = sq_edge / cells[0]

    #########
    # Here calculate the default fontsize. The text fits nicely in the square for 5x5 cells and fontsize 14.
    fontsize = 15
    scale_factor = 5 / cells[0]
    fontsize = int(scale_factor * fontsize)
    #########

    circ = Circle((0, 0), rad, facecolor=[.7, .7, .7])

    clip_size = 0.95 * rad * 2
    rect = Rectangle((-rad, rad - clip_size), 2 * rad, clip_size, facecolor="none", edgecolor="none")
    ax.add_artist(circ)
    ax.add_artist(rect)
    circ.set_clip_path(rect)

    for ii in range(1, cells[0] + 1):
        for jj in range(1, cells[1] + 1):
            x_corner = -sq_edge / 2 + (jj - 1) * single_cell_side
            y_corner = sq_edge / 2 - ii * single_cell_side

            label_kwargs = {'ha': 'right', 'va': 'center', 'weight': 'bold', 'fontsize': 15}

            if jj == 1:
                letter = str(ii)
                ax.text(-sq_edge / 2 - pad_letter, y_corner + single_cell_side / 2, letter, label_kwargs)
            if ii == 1:
                label_kwargs['ha'] = 'center'
                label_kwargs['va'] = 'bottom'
                letter = chr(ord('A') + (jj - 1))
                ax.text(x_corner + single_cell_side / 2, sq_edge / 2 + pad_letter, letter, label_kwargs)
            if ((ii, jj) != (1, 1)) and ((ii, jj) != (cells[0], 1)) and ((ii, jj) != (1, cells[1])) and (
                    (ii, jj) != (cells[0], cells[1])):
                if chip_info[ii - 1][jj - 1] is None:
                    recty = Rectangle((x_corner, y_corner), single_cell_side, single_cell_side,
                                      facecolor= [.4,.4,.4], edgecolor='k', hatch=r'/...')
                else:
                    freq, Q, extra_info = chip_info[ii - 1][jj - 1]

                    if Q < bad_thresh:
                        facecolor = 'red'
                    elif Q >= good_thresh:
                        facecolor = 'limegreen'
                    else:
                        facecolor = 'orange'
                    recty = Rectangle((x_corner, y_corner), single_cell_side, single_cell_side,
                                      facecolor=facecolor, edgecolor='k', alpha=.7)
                    if extra_info is None:
                        annotate_string = r'$\nu_0$' + ': {:.3f} MHz\n\nQ: {:.1f} M'.format(freq / 1e6, Q / 1e6)
                    else:
                        annotate_string = r'$\nu_0$' + ': {:.3f} MHz\n\nQ: {:.1f} M\n\n{:s}'.format(freq / 1e6, Q / 1e6, extra_info)
                    ax.annotate(annotate_string,
                                (x_corner + single_cell_side / 2, y_corner + single_cell_side / 2), ha='center',
                                va='center',
                                fontsize=fontsize)
                ax.add_artist(recty)

    plt.savefig(savedir, bbox_inches = 'tight')


def get_Q_factor(ringdown, res_freq, threshold=200e-6, p0_nogamma=None, fitting_func = nlin_rdown, *args, **kwargs):
    """
    Lazy functio to get the Q factor. It already does the gamma estimation, the rest of the guesses are left to the user
    and they are appended to the gamma guess. NOTICE: the fitting function needs to have the decay rate as its first
    free parameter.
    :param ringdown: (n,2) np.ndarray, containing the time axis and the ringdown data
    :param res_freq: The resonance frequency
    :param threshold: The threshold that's used to remove the background when estimating the gamma from the data
    :param fitting_func: The function to be used to fit the data
    :param args: Passed to the core scipy.optimize.curve_fit function
    :param kwargs: Passed to the core scipy.optimize.curve_fit function
    :return: Tuple containing (best fit estimates, Q factor, covariance matrix)
    """
    timetrace, decay = ringdown[:, 0], ringdown[:, 1]
    decay /= decay.max()
    data_above_thresh = decay[decay > threshold]
    gamma_guess = (-2 * np.diff(np.log(data_above_thresh)) / (timetrace[1] - timetrace[0])).mean()

    if p0_nogamma is None:
        p0_nogamma = [1,]*len(signature(fitting_func).parameters) - 2 #-2 because x axis and decay are excluded
    fit_guess = [gamma_guess] + p0_nogamma
    if fit_guess[0] < 0:
        print("Negative derivative estimated. Avoided fitting.")
        fit_result, Q_factor = None, None
    else:
        fit_result, cov_mat = curve_fit(fitting_func, timetrace, decay, p0=fit_guess, *args, **kwargs)

        Q_factor = 2 * np.pi * res_freq / fit_result[0]
    return fit_result, Q_factor, cov_mat