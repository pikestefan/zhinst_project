import numpy as np
import h5py
from pathlib import Path
import shutil


def remap_ZIfiles_dir(
    parent_fold,
    start_stream=None,
    stop_stream=None,
    target_dir=None,
    experiment_name="",
    init_counter=0,
):
    """
    Function that remaps the h5 files saved by Zurich Instruments lock-in into a single folder. The h5 files are named
    with an optional prepended experiment name, and are numbered starting from the init_counter
    :param parent_fold: The folder into which the original stream folders are saved.
    :param start_stream: optional, The first file that needs to be remapped. Default is first.
    :param stop_stream: optional, the last file that needs to be remapped. Default is last.
    :param target_dir: The folder into which the files will be copied.
    :param experiment_name: optional, the name of the experiment to prepend to the h5 file names.
    :param init_counter: optional, the number ID of the first file name.
    """
    if type(parent_fold) is str:
        parent_fold = Path(parent_fold)

    if type(target_dir) is str:
        target_dir = Path(target_dir)

    folder_names = [x for x in parent_fold.iterdir() if x.is_dir()]

    if start_stream is None:
        start_ind = 0
    else:
        start_fold = parent_fold / start_stream
        start_ind = folder_names.index(start_fold)
    if stop_stream is None:
        stop_ind = len(folder_names) - 1
    else:
        stop_fold = parent_fold / stop_stream
        stop_ind = folder_names.index(stop_fold)

    chosen_folders = folder_names[start_ind : stop_ind + 1]

    if not target_dir.is_dir():
        target_dir.mkdir()
    for ii, sub_fold in enumerate(chosen_folders):
        fold_els = list(sub_fold.glob("*.h5"))
        if len(fold_els) == 1:
            item_path = sub_fold / fold_els[0]

            target_filename = "{:d}".format(init_counter + ii)
            if len(target_filename) == 1:
                target_filename = experiment_name + "0" + target_filename

            target_filename += ".h5"

            target_filename = target_dir / target_filename

            if ii == 0 and len(list(target_dir.glob("*.h5"))) > 0:
                print("Folder already contains files, copying aborted.")
                break

            shutil.copy(item_path, target_filename)


def get_h5_signals(h5file):
    """
    Function that imports h5 data into a dictionary. If more than one chunk is saved into the hdf5 file, it appends
    the data of from different chunks to the same signals and demods, and returns a dictionary of the signals.
    Each dictionary value is a Mx2 array. The first column is the timestamp, the second the values.
    :param h5file: a h5file saved by a ZI lock-in.
    :return: Dictionary containing the timestamps and values for each demodulator and signals that was saved.
    """
    with h5py.File(h5file, "r") as file:
        # First get the available signals, assuming there's gonna be always a 000 chunk
        demod_path = ""
        group_amt = 1
        while group_amt == 1:
            if demod_path == "":
                group_list = list(file["000"].keys())
            else:
                group_list = list(file[f"000/{demod_path}"].keys())
            group_amt = len(group_list)

            if group_amt == 1:
                demod_path = demod_path + group_list[0] + "/"

            if group_amt == 1 and group_list[0] == "demods":
                available_demods = list(file[f"000/{demod_path}"].keys())
                break

        # Now make a dictionary with the available signals
        data_dictionary = dict()
        for demod in available_demods:
            sub_signals = list(file[f"000/{demod_path}/{demod}"].keys())
            for sub_sig in sub_signals:
                data_dictionary[f"{demod}/{sub_sig}"] = np.empty((0, 2))

        # Now make append the data to the dictionary
        for chunk in file.keys():
            for signal in data_dictionary.keys():
                data_path = f"{chunk}/{demod_path}{signal}"
                timestamp = file[data_path]["timestamp"][:]
                data = file[data_path]["value"][:]
                bundled = np.hstack((timestamp[:, None], data[:, None]))
                data_dictionary[signal] = np.vstack((data_dictionary[signal], bundled))

    return data_dictionary


def get_base_h5path(h5file):
    """
    Finds the base path to the demodulators, in a standard hdf5 path save by the ZI lock-in. Not to be used with
    custom saved files. Example of basepath: dev1347/demods/ (yes, this function is pure laziness).
    :param h5file: the h5file path
    :return: string, the base path
    """

    demod_path = ""
    group_amt = 1
    group_list = [""]
    with h5py.File(h5file, "r") as file:
        while group_amt == 1 and not (group_list[0] == "demods"):
            if demod_path == "":
                group_list = list(file.keys())
            else:
                group_list = list(file[demod_path].keys())

            group_amt = len(group_list)
            if group_amt == 1:
                demod_path = demod_path + group_list[0] + "/"

    return demod_path


def import_ringdowns(
    folder_path, signal_demod="0", reference_demod="1", file_type="custom"
):
    if type(folder_path) is str:
        folder_path = Path(folder_path)
    if file_type not in ["custom", "zi"]:
        raise Exception(
            "Please provide an accepted file type. Options are 'custom' or 'zi'."
        )

    h5file_list = list(map(str, folder_path.glob("*.h5")))
    if file_type == "zi":
        common_h5_path = get_base_h5path(h5file_list[0])

    ringdown_list = []
    for h5file in h5file_list:
        if file_type == "custom":
            data_dictionary = get_h5_signals(h5file)
            signal_name = [
                signal for signal in data_dictionary.keys() if signal[0] == signal_demod
            ][0]
            ref_name = [
                signal
                for signal in data_dictionary.keys()
                if signal[0] == reference_demod
            ][0]

            signal_array, ref_array = (
                data_dictionary[signal_name],
                data_dictionary[ref_name],
            )

            tstamp = signal_array[:, 0]
            signal_norm = signal_array[:, 1]
            trigger = ref_array[:, 1]
        else:
            with h5py.File(h5file, "r") as file:
                tstamp = file[common_h5_path + f"{signal_demod}/sample.x/timestamp"][:]

                x_sig, y_sig = (
                    file[common_h5_path + f"{signal_demod}/sample.x/value"],
                    file[common_h5_path + f"{signal_demod}/sample.y/value"],
                )
                x_ref, y_ref = (
                    file[common_h5_path + f"{reference_demod}/sample.x/value"],
                    file[common_h5_path + f"{reference_demod}/sample.y/value"],
                )

                signal_norm = np.abs(x_sig[:] + 1j * y_sig[:])

                trigger = np.abs(x_ref[:] + 1j * y_ref[:])

        trigger = np.where(trigger >= trigger.mean(), 1, 0).astype(int)

        shortest_len = min(len(signal_norm), len(trigger))

        output_array = [tstamp, signal_norm, trigger]

        output_array = [array[:shortest_len] for array in output_array]

        ringdown_list.append(output_array)

    return ringdown_list


def import_ringdowns_v2(
    folder_path, signal_demod="0", reference_demod="1", file_type="custom"
):
    # Doesn't rescale the reference to be either zero or one, just imports the raw data
    if type(folder_path) is str:
        folder_path = Path(folder_path)
    if file_type not in ["custom", "zi"]:
        raise Exception(
            "Please provide an accepted file type. Options are 'custom' or 'zi'."
        )

    h5file_list = list(map(str, folder_path.glob("*.h5")))
    if file_type == "zi":
        common_h5_path = get_base_h5path(h5file_list[0])

    ringdown_list = []
    for h5file in h5file_list:
        if file_type == "custom":
            data_dictionary = get_h5_signals(h5file)
            signal_name = [
                signal for signal in data_dictionary.keys() if signal[0] == signal_demod
            ][0]
            ref_name = [
                signal
                for signal in data_dictionary.keys()
                if signal[0] == reference_demod
            ][0]

            signal_array, ref_array = (
                data_dictionary[signal_name],
                data_dictionary[ref_name],
            )

            tstamp = signal_array[:, 0]
            signal_norm = signal_array[:, 1]
            trigger = ref_array[:, 1]
        else:
            with h5py.File(h5file, "r") as file:
                tstamp = file[common_h5_path + f"{signal_demod}/sample/timestamp"][:]

                x_sig, y_sig = (
                    file[common_h5_path + f"{signal_demod}/sample/x"],
                    file[common_h5_path + f"{signal_demod}/sample/y"],
                )
                x_ref, y_ref = (
                    file[common_h5_path + f"{reference_demod}/sample/x"],
                    file[common_h5_path + f"{reference_demod}/sample/y"],
                )

                signal_norm = np.abs(x_sig[:] + 1j * y_sig[:])

                trigger = np.abs(x_ref[:] + 1j * y_ref[:])

        shortest_len = min(len(signal_norm), len(trigger))

        output_array = [tstamp, signal_norm, trigger]

        output_array = [array[:shortest_len] for array in output_array]

        ringdown_list.append(output_array)

    return ringdown_list


if __name__ == "__main__":
    res = get_h5_signals(
        r"Z:\membrane\SLAB interferometer\data\2021\04\12\DEGPAR02\phase_sweeps\mode0\parametric_100mV\00.h5"
    )
    print(res)
