from zhinstlib.core_classes.zinst_device import ziVirtualDevice
from zhinstlib.helpers.helper_funcs import get_device_props
from zhinstlib.helpers.prompt_widget import prompt_at_overwrite
import time
import numpy as np
from pathlib import Path
import sys

############################
###### Parameter list ######
############################

# Resonator properties
Q_approximate = 5e7
res_freq = 1.22910009e6

gamma_estimate = res_freq / Q_approximate

# Lock-in settings
device_id = 'dev1347'
output_voltage = 20e-3  # Units in Volts
resonant_demod = 0 # The demodulator used for the resonant driving
sweep_demod = 1 # The demod corresponding to the row to sweep the driving
reference_demod = 2 # The demod that acquires the synch output channel
output_channel = 0
desired_signals = 'r'

# Experiment settings
ringdown_repeat = 3
sweep_voltage = np.linspace(0, 1, 11)

# Optimizer settings
opt_thresh = 1e-3
integration_time = 0.1  # seconds
stepsize = 0.5  # Hz
itermax = 100
optimizer_kwargs = {'wait_time': 1/gamma_estimate,
                    'min_delta': opt_thresh,
                    'stepsize': stepsize,
                    'itermax': itermax,
                    'integration_time': integration_time}

# Saving settings
burst_duration = 1 # seconds
file_directory = r'C:\Users\QMPL\Documents\Local_exp_runs\parametric\degpar02\ringdowns\mode0\deamplified'
file_name = 'stream'
saving_kwargs = {'saving_dir': file_directory,
                 'saving_fname': file_name,
                 }
save_to_file = True

############################
### Start the experiment ###
############################
#Check if saving folder exist, otherwise create it. If target folder is not empty, prompt the user.
path_to_dir = Path(file_directory)
path_to_file = path_to_dir / Path(file_name)
if not path_to_dir.is_dir():
    path_to_dir.mkdir()
    print(f"Created {str(path_to_dir)}")
else:
    if any(path_to_dir.iterdir()):
        keep_going = prompt_at_overwrite('Folder already contains elements, proceed appending files here?')

        if not keep_going:
            print("Experiment aborted.")
            sys.exit(0)


# First calculate the wait time for the ringdown...
ringdown_acq_time = 3/gamma_estimate

# Set the readout time for the ringdown experiment
initial_sleep_time = 1.5 * burst_duration
read_duration = initial_sleep_time + 2*ringdown_acq_time*ringdown_repeat + ringdown_acq_time
stream_read_kwargs = {'read_duration': read_duration,
                      'burst_duration': burst_duration}


device_props = get_device_props(device_id)
zi_device = ziVirtualDevice(device_id,
                            device_props['serveraddress'],
                            device_props['serverport'],
                            device_props['apilevel'])

zi_device.set_output_volt(resonant_demod, voltage=output_voltage, column=output_channel)
zi_device.set_output_volt(sweep_demod, voltage=0, column=output_channel)

# Check that the output channels are on, otherwise turn them on
if not zi_device.get_output_state(output_channel):
    zi_device.set_output_state(output_channel, True)

if not zi_device.get_demod_output(resonant_demod, output_channel):
    zi_device.set_demod_output(resonant_demod, on_state=True, column=output_channel)

if not zi_device.get_demod_output(sweep_demod, output_channel):
    zi_device.set_demod_output(sweep_demod, on_state=True, column=output_channel)

daqmodule_name, sus_signal_paths = zi_device.set_subscribe_daq([resonant_demod, reference_demod],
                                                               desired_signals, save_files=save_to_file,
                                                               **stream_read_kwargs, **saving_kwargs)
zi_device.sync()
print("Experiment is starting.")
for ii, voltage in enumerate(sweep_voltage):
    zi_device.set_output_volt(sweep_demod, voltage=voltage, column=output_channel)
    print("About to optimize.")
    zi_device.optimize_freq_v2(resonant_demod, **optimizer_kwargs)

    zi_device.execute_daqmodule(daqmodule_name)
    time.sleep(initial_sleep_time)
    for rep in range(ringdown_repeat):
        zi_device.set_demod_output(resonant_demod, on_state=False)
        time.sleep(ringdown_acq_time)
        zi_device.set_demod_output(resonant_demod, on_state=True)
        if rep < ringdown_repeat-1:  # Wait to recover only in the middle of acquisition
            time.sleep(ringdown_acq_time)
    zi_device.set_demod_output(resonant_demod, on_state=True)
    zi_device.read_daq_module(daqmodule_name, sus_signal_paths, save_to_dictionary=False, save_on_file=save_to_file)

print("Experiment completed.")