from zhinstlib.core.zinst_device import ziVirtualDevice
from zhinstlib.helpers.helper_funcs import get_device_props
from zhinstlib.helpers.prompt_widget import prompt_at_overwrite
import time
import numpy as np
import sys
from pathlib import Path

############################
###### Parameter list ######
############################

# Resonator properties
Q_approximate = 1e7
res_freq = 1.22912662e6

gamma_estimate = res_freq / Q_approximate

# Lock-in settings
device_id = 'dev1347'
output_voltage = 50e-3  # Units in Volts, resonant driving voltage
resonant_demod = 0 # The demodulator used for the resonant driving
sweep_demod = 1 # The demod corresponding to the row to sweep the driving
output_channel = 0
desired_signals = ['x', 'y']

# Experiment settings
sweep_parameter = 'phase'
calibration_trace_acq_time = 80  # seconds
exp_acquisition_time = 40  # seconds
sweeper_fixed_phase = 160  # Fixed phase when amplitude is swept
sweeper_fixed_amplitude = 500e-3 # volts, used when phase is swept
sweep_values = np.arange(-170, 170.1, 20)
initial_sleep_time = 5

# Optimizer settings
opt_thresh = 1e-3
integration_time = 1  # seconds
stepsize = 0.5  # Hz
itermax = 500
optimizer_kwargs = {'wait_time': gamma_estimate,
                    'min_delta': opt_thresh,
                    'stepsize': stepsize,
                    'itermax': itermax,
                    'integration_time': integration_time}

# Saving settings
burst_duration = 1 # seconds
file_directory = r'C:\Users\QMPL\Documents\local_exp_runs\parametric\deg04\phase_sweeps\mode0\500mV'
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
if not path_to_dir.is_dir():
    path_to_dir.mkdir()
    print(f"Created {str(path_to_dir)}")
else:
    if any(path_to_dir.iterdir()):
        keep_going = prompt_at_overwrite('Folder already contains elements, proceed appending files here?')

        if not keep_going:
            print("Experiment aborted.")
            sys.exit(0)
# Set the readout time for the general experiment
#initial_sleep_time = 0 * burst_duration
read_duration = initial_sleep_time + exp_acquisition_time

calibration_read_kwargs = {'read_duration': calibration_trace_acq_time,
                           'burst_duration': burst_duration}

stream_read_kwargs = {'read_duration': read_duration,
                      'burst_duration': burst_duration}


device_props = get_device_props(device_id)
zi_device = ziVirtualDevice(device_id,
                            device_props['serveraddress'],
                            device_props['serverport'],
                            device_props['apilevel'])

print(output_voltage)
zi_device.set_output_volt(resonant_demod, voltage=output_voltage, column=output_channel)
zi_device.set_output_volt(sweep_demod, voltage=0, column=output_channel)

# Check that the output channels are on, otherwise turn them on
if not zi_device.get_output_state(output_channel):
    zi_device.set_output_state(output_channel, True)

if not zi_device.get_demod_output(resonant_demod, output_channel):
    zi_device.set_demod_output(resonant_demod, on_state=True, column=output_channel)

daqmodule_name, sus_signal_paths = zi_device.set_subscribe_daq(resonant_demod,
                                                               desired_signals, save_files=save_to_file,
                                                               **calibration_read_kwargs, **saving_kwargs)
zi_device.sync()
print("Experiment is starting.")
print("Acquiring calibration trace.")
print("About to optimize.")
#zi_device.optimize_freq_v2(resonant_demod, **optimizer_kwargs)
time.sleep(initial_sleep_time)
zi_device.execute_daqmodule(daqmodule_name)
time.sleep(calibration_trace_acq_time)
zi_device.read_daq_module(daqmodule_name, sus_signal_paths, save_to_dictionary=False, save_on_file=save_to_file)
print("Acquired calibration trace.")

print("Setting up the sweep experiment.")
if not zi_device.get_demod_output(sweep_demod, output_channel):
    zi_device.set_demod_output(sweep_demod, on_state=True, column=output_channel)

daqmodule_name, sus_signal_paths = zi_device.set_subscribe_daq(resonant_demod,
                                                               desired_signals, save_files=save_to_file,
                                                               **stream_read_kwargs, **saving_kwargs)
zi_device.sync()
print("Experiment is starting.")
for ii, sweep_value in enumerate(sweep_values):
    if sweep_parameter == 'phase':
        zi_device.set_demod_phase(sweep_demod, phase=sweep_value)
        if ii == 0:
            zi_device.set_output_volt(sweep_demod, voltage=sweeper_fixed_amplitude, column=output_channel)
    elif sweep_parameter == 'amplitude':
        zi_device.set_output_volt(sweep_demod, voltage=sweep_value, column=output_channel)
        if ii == 0:
            zi_device.set_demod_phase(sweep_demod, phase=sweeper_fixed_phase)
    else:
        raise Exception("Sweep parameter not defined yet")

    print("About to optimize.")
    #zi_device.optimize_freq_v2(resonant_demod, **optimizer_kwargs)
    time.sleep(initial_sleep_time)
    zi_device.execute_daqmodule(daqmodule_name)
    time.sleep(exp_acquisition_time)
    zi_device.read_daq_module(daqmodule_name, sus_signal_paths, save_to_dictionary=False, save_on_file=save_to_file)

print("Completed.")
