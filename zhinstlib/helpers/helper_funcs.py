import zhinst.ziPython as zi
import h5py
import inspect
from pathlib import Path

def get_device_props(device_id):
    discovery = zi.ziDiscovery()
    device_id = discovery.find(device_id)
    device_props = discovery.get(device_id)

    return device_props


def save_vars_hdf5(file_directory, filename='settings.txt'):
    if isinstance(file_directory, str):
        file_directory = Path(file_directory)
    file_directory = file_directory / filename
    with open(file_directory, 'w') as file:
        print(__name__)
        print(globals())
        for var in dir(__file__):
            value = globals()[var]
            if ('__' not in var) and not (inspect.ismodule(value) or
                                          inspect.isfunction(value) or
                                          inspect.isclass(value)):
                file.write(f"{var}: {value}\n")
