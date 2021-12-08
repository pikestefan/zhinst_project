from zhinstlib.core_classes.zinst_device import ziVirtualDevice
from zhinstlib.helpers.helper_funcs import get_device_props
from zhinstlib.helpers.prompt_widget import prompt_at_overwrite
import time
import numpy as np
import sys
from pathlib import Path

"""
Experiment that sweeps the parametric frequency detuning, and then sweeps the phase of the parametric drive.
Files are saved sequentially. I.e. if there are N detuning values and M phase values, the number of files is NxM.
The first M files will be relative to the first detuning values, and so on.
"""

############################
###### Parameter list ######
############################

# Resonator properties
Q_approximate = 1e6
res_freq = 1.16917929e6

gamma_estimate = res_freq / Q_approximate

# Lock-in settings
device_id = 'dev1347'
output_voltage = 20e-3  # Volts, resonant driving voltage
resonant_demod = 0 # The demodulator used for the resonant driving
sweep_demod = 1 # The demod corresponding to the row to sweep the driving
resonant_demod_oscillator = 0
sweep_demod_oscillator = 1
output_channel = 0
desired_signals = 'r'

# Experiment settings
acquire_calib_trace = True
calibration_trace_acq_time = 60  # seconds
exp_acquisition_time = 30  # seconds
sweeper_amplitude = 1  # Volts
phase_sweep_values = np.linspace(-170, 180, 15)
detuning_values = np.linspace(-10, 10, 11)  # Hz

settings_infofile = {'device_id': device_id,
                     'output voltage': output_voltage,
                     'resonant demod': resonant_demod,
                     'sweep demod': sweep_demod,
                     'resonant demod oscillator': resonant_demod_oscillator,
                     'sweep demod oscillator': sweep_demod_oscillator,
                     'output channel': output_channel,
                     'desired signals': desired_signals,
                     'sweeper amplitude': sweeper_amplitude,
                     'phase sweep values': phase_sweep_values,
                     'detuning values': detuning_values}

# Optimizer settings
opt_thresh = 1e-3
integration_time = 0.1  # seconds
stepsize = 0.2  # Hz
itermax = 100
optimizer_kwargs = {'wait_time': gamma_estimate,
                    'min_delta': opt_thresh,
                    'stepsize': stepsize,
                    'itermax': itermax,
                    'integration_time': integration_time}

# Saving settings
local_exp_folder = Path(r'C:\Users\QMPL\Documents\local_exp_runs\parametric\degpar02')
file_directory = (local_exp_folder / 'detuning_phase_sweeps' / 'mode0' /
                  'parametric_{:.0f}mV'.format(sweeper_amplitude*1e3))
file_directory = str(file_directory)
burst_duration = 1  # seconds
file_name = 'stream'
saving_kwargs = {'saving_dir': file_directory,
                 'saving_fname': file_name,
                 }
save_to_file = True

############################
### Start the experiment ###
############################
if save_to_file:
    # Check if saving folder exist, otherwise create it. If target folder is not empty, prompt the user.
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

    #Create a file with the exp settings
    info_file = path_to_dir / 'exp_settings.txt'
    all_settings = [{'experiment type': __file__.split('/')[-1][:-3]}, settings_infofile, optimizer_kwargs,
                    saving_kwargs]
    with open(info_file, 'w') as file:
        for setting_chunk in all_settings:
            for key, value in setting_chunk.items():
                file.write(f'{key}: {value}\n')


# Set the readout time for the general experiment
initial_sleep_time = 0 * burst_duration
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

zi_device.set_output_volt(resonant_demod, voltage=output_voltage, column=output_channel)
zi_device.set_demod_oscillator(resonant_demod, resonant_demod_oscillator)

# Check that the output channels are on, otherwise turn them on
if not zi_device.get_output_state(output_channel):
    zi_device.set_output_state(output_channel, True)

if not zi_device.get_demod_output(resonant_demod, output_channel):
    zi_device.set_demod_output(resonant_demod, on_state=True, column=output_channel)

# But turn off the parametric drive, if it is on
if zi_device.get_demod_output(sweep_demod, output_channel):
    zi_device.set_demod_output(sweep_demod, on_state=False, column=output_channel)

daqmodule_name, sus_signal_paths = zi_device.set_subscribe_daq(resonant_demod,
                                                               desired_signals, save_files=save_to_file,
                                                               **calibration_read_kwargs, **saving_kwargs)
zi_device.sync()
print("Experiment is starting.")
if acquire_calib_trace:
    print("Acquiring calibration trace.")
    print("About to optimize.")
    zi_device.optimize_freq_v2(resonant_demod, **optimizer_kwargs)
    time.sleep(initial_sleep_time)
    zi_device.execute_daqmodule(daqmodule_name)
    time.sleep(exp_acquisition_time)
    zi_device.read_daq_module(daqmodule_name, sus_signal_paths, save_to_dictionary=False, save_on_file=save_to_file)
    print("Acquired calibration trace.")

print("Setting up the sweep experiment.")
if not zi_device.get_demod_output(sweep_demod, output_channel):
    zi_device.set_demod_output(sweep_demod, on_state=True, column=output_channel)


zi_device.set_demod_oscillator(sweep_demod, sweep_demod_oscillator)
zi_device.set_demod_harmonic(sweep_demod, 1)
zi_device.set_output_volt(sweep_demod, voltage=sweeper_amplitude, column=output_channel)

daqmodule_name, sus_signal_paths = zi_device.set_subscribe_daq(resonant_demod,
                                                               desired_signals, save_files=save_to_file,
                                                               **stream_read_kwargs, **saving_kwargs)
zi_device.sync()
print("Experiment is starting.")
for ii, sweep_value in enumerate(detuning_values):
    for jj, phase in enumerate(phase_sweep_values):
        # First turn off the parametric demod and optimize
        zi_device.set_demod_output(sweep_demod, on_state=False)
        zi_device.set_demod_phase(sweep_demod, phase)
        zi_device.sync()
        print("About to optimize.")
        zi_device.optimize_freq_v2(resonant_demod, **optimizer_kwargs)

        # Find the new optimized frequency, then set the parametric drive to be detuned from it
        optimized_freq = zi_device.get_oscillator_freq(resonant_demod_oscillator)
        zi_device.set_oscillator_freq(sweep_demod_oscillator, 2*optimized_freq + sweep_value)
        zi_device.set_demod_output(sweep_demod, on_state=True)
        zi_device.sync()

        # Acquire the data
        time.sleep(initial_sleep_time)
        zi_device.execute_daqmodule(daqmodule_name)
        time.sleep(exp_acquisition_time)
        zi_device.read_daq_module(daqmodule_name, sus_signal_paths, save_to_dictionary=False, save_on_file=save_to_file)

print("Completed.")