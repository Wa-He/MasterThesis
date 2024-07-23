# -*- coding: utf-8 -*-
import time
import tkinter as tk
from tkinter import filedialog
import pandas as pd
import numpy as np
import scipy as sc
from sklearn.linear_model import LinearRegression
import matplotlib.pyplot as plt
import matplotlib as mpl
import matplotlib.dates as mdates
from matplotlib.dates import HourLocator, DateFormatter
from matplotlib.widgets import Button, RadioButtons, TextBox
import os
from tqdm import tqdm
from joblib import Parallel, delayed
import psutil
import multiprocessing


class Output_Dummy:
    def insert(self, start, string):
        print(string)

    def delete(self, start, end):
        pass


class THS_Control:
    """
    Class to control transient hot strip measurements within the TVAC.
    """

    def __init__(self, resource_manager):
        self.running = False
        self.end = False
        self.filename = None
        self.create_new_file = False

        # measurement modes
        self.start_measurement_manually = False  # starts if set true
        self.start_idle = False  # starts if set true
        self.start_autocycle = False  # starts if set true
        self.start_autocycle_non_stat = False
        self.start_autosweep = False
        self.current_ths_mode = None  # remembers current measurement mode

        self.current_power_mode = None  # 'low' or 'high' power
        self.default_voltage = 1.3  # default measuring voltage (high power) (adjustable)
        self.measure_voltage = self.default_voltage
        self.SET_measure_voltage = False
        self.temp_gradient = 1  # initial temperature gradient for autosweep (K/h)
        self.SET_temp_gradient = False
        self.time_high_power_change = None  # time when power was changed to 'high'
        self.heating_time_interval = pd.Timedelta(1, 'h')  # timedelta to return to low power (adjustable)
        self.SET_heating_time = False
        self.time_at_last_stationary_check = None  # timestamp
        self.thermal_conductivities_to_check = []  # thermal conductivities array (at same target temp, check validity)
        self.autocycle_phase = 'wait'
        self.last_measurement_time = pd.Timestamp('now')  # initialize time for non stat measurements
        self.autosweep_phase = 'wait'

        # measurement variables
        self.current_temp = None
        self.current_target_temp = None
        self.target_range = 3  # allowed mean_temp deviation for finding stationary states (K) (bad calibration)
        self.target_temperatures = []
        self.target_temperatures_counter = 0

        self.thermal_conductivities = []
        self.thermal_conductivities_errors = []
        self.thermal_diffusivities = []
        self.thermal_diffusivities_errors = []
        self.measured_temperatures = []
        self.measured_temperatures_errors = []

        # Devices
        self.rm = resource_manager  # pyvisa resource manager (initialized in gui)
        self.power_supply = None  # Siglent power supply
        self.SDM = None  # Siglent digital multimeter
        self.latest_feedback = None  # latest measurement

        # Resistance-temperature parameters and fit
        self.R0 = 6.0166  # temp(res) fit parameter as calibrated in ice water, std: 0.003. first cal: 6.036, std 0.007, init 6.419 by DLR/Moritz?
        self.A = 0.004308  # temp(res) fit parameter, as calibrated by DLR
        self.B = -4.91 * 10 ** -7  # temp(res) fit parameter, as calibrated by DLR
        self.C = 1.41 * 10 ** -12  # temp(res) fit parameter, as calibrated by DLR
        temp = np.arange(-273.15, 1000, 0.05)
        res = self.R0 * self.C * (
                    temp - 100) * temp ** 3 + self.R0 * self.B * temp ** 2 + self.R0 * self.A * temp + self.R0
        self.temperature_fit_func = sc.interpolate.interp1d(x=res, y=temp, fill_value=np.nan, bounds_error=False)
        # THS dimensions
        self.ths_length = 0.072
        self.ths_length_err = 0.002
        self.ths_width = 0.002
        self.probing_depth = 0.035

        # evaluation parameters
        self.stationary_time_interval = pd.Timedelta(60, 'min')  # time the temperature has to stay stable
        self.SET_stationary_time = False
        self.max_temp_deviation = 0.1  # max temperature deviation (kelvin) allowed from targeted value
        self.min_ratio_in_interval = 0.95  # allows some percent of values to be outside of max temp interval
        self.max_temp_deviation_gradient = 0.1
        self.min_ratio_in_interval_gradient = 0.9  # max values outside of interval for temp gradient correction fit
        self.time_span_non_stat_measurements = 6 * self.heating_time_interval  # interval before and after non stationary measurements for fit

        self.shunt_resistance = 47.1291  # mean from shunt determination
        self.shunt_resistance_err = 0.0006  # std from shunt determination
        self.shunt_volt_error = 0.0005  # used only for small temp fluctuations and mult uncertainty # variation evaluated with ambient temperature changes (2024-07-02): 0.005
        self.voltage_error = 0.00005  # signal variation evaluated at temperature stable measurements (2024-07-02)

        # gui elements
        self.output = Output_Dummy()
        self.error_output = Output_Dummy()

    def start_THS(self, SDM, input_voltage, input_heating_time, input_list, input_stationary_time, input_temp_gradient, output, error_output):
        """
        Starts and sets up THS heat conductivity measurements using a separate digital multimeter for measurements.
        Different modes (idle, manual, auto) are available (Input from gui needed!).
        """
        self.SDM = SDM
        self.output = output
        self.error_output = error_output

        output.delete(0, tk.END)
        output.insert(0, 'Connecting...')

        if not self.SDM.active:
            error_output.delete(0, tk.END)
            error_output.insert(0, 'THS: Activate SDM first!')
            return

        if not self.running:
            self.running = True
            self.end = False

        if not self.end and self.running:
            # initialize file to save data
            start_time = pd.Timestamp.now()
            self.filename = start_time.strftime('%Y-%m-%d-%H-%M-%S') + "_THS"
            self.write_to_file(init=True)
            # start power supply at low mode
            self.start_power_supply()
            self.set_low_power()
            # initialize gui entries
            input_stationary_time.delete(0, tk.END)
            input_stationary_time.insert(0, self.stationary_time_interval.total_seconds() / 60)
            input_heating_time.delete(0, tk.END)
            input_heating_time.insert(0, self.heating_time_interval.total_seconds() / 60)
            input_voltage.delete(0, tk.END)
            input_voltage.insert(0, self.default_voltage)
            input_temp_gradient.delete(0, tk.END)
            input_temp_gradient.insert(0, self.temp_gradient)

            time.sleep(2)
            # main loop
            while True:
                # stop condition
                if self.end:
                    self.stop_THS()
                    self.output.delete(0, tk.END)
                    self.output.insert(0, 'THS disconnected!')
                    break

                # write latest data to file
                self.write_to_file()

                # create new file if backup is required
                if self.create_new_file:
                    print(pd.Timestamp.now().strftime('%X'), 'THS: new file created for backup')
                    self.filename = pd.Timestamp('now').strftime('%Y-%m-%d-%H-%M-%S') + "_THS"
                    self.write_to_file(init=True)
                    self.create_new_file = False

                if self.SET_stationary_time:
                    try:
                        self.stationary_time_interval = pd.Timedelta(float(input_stationary_time.get()), 'min')
                    except Exception as error:
                        print(pd.Timestamp('now').strftime('%X'), 'Error setting stationary time interval', error)
                    self.output.delete(0, tk.END)
                    self.output.insert(0, 'Stationary time interval set!')
                    self.SET_stationary_time = False

                if self.SET_heating_time:
                    try:
                        self.heating_time_interval = pd.Timedelta(float(input_heating_time.get()), 'min')
                        self.time_span_non_stat_measurements = 6 * self.heating_time_interval
                    except Exception as error:
                        print(pd.Timestamp('now').strftime('%X'), 'Error setting heating time interval', error)
                    self.output.delete(0, tk.END)
                    self.output.insert(0, 'Heating time interval set!')
                    self.SET_heating_time = False

                if self.SET_measure_voltage:
                    try:
                        self.measure_voltage = float(input_voltage.get())
                    except Exception as error:
                        print(pd.Timestamp('now').strftime('%X'), 'Error setting stationary time interval', error)
                    self.output.delete(0, tk.END)
                    self.output.insert(0, 'Measure voltage set!')
                    self.SET_measure_voltage = False

                if self.SET_temp_gradient:
                    try:
                        input = input_temp_gradient.get()
                        sign = 1
                        if input.startswith('-'):
                            sign = -1
                        self.temp_gradient = sign * abs(float(input))
                        print(pd.Timestamp('now').strftime('%X'), 'Temp. gradient set: ', self.temp_gradient)

                    except Exception as error:
                        print(pd.Timestamp('now').strftime('%X'), 'Error setting temp. gradient', error)
                    self.output.delete(0, tk.END)
                    self.output.insert(0, 'Temp. gradient set!')
                    self.SET_temp_gradient = False

                ### choose control mode based on gui input (changed in separate functions)
                # mode: idle
                if self.start_idle:
                    self.current_ths_mode = 'idle'
                    self.target_temperatures_counter = 0
                    input_list.reset_marking()  # reset for autocycle
                    if self.current_power_mode != 'low':
                        self.set_low_power()


                # mode: manual
                elif self.start_measurement_manually:
                    self.current_ths_mode = 'manual'
                    self.target_temperatures_counter = 0
                    input_list.reset_marking()  # reset for autocycle
                    # initially set power mode to high
                    if self.current_power_mode != 'high':
                        self.set_high_power(self.measure_voltage)
                        self.time_high_power_change = pd.Timestamp('now')
                        self.create_new_file = True  # start new file for measurement
                    # stop measurement after specified time and calculate thermal conductivity
                    elif self.current_power_mode == 'high' and self.time_high_power_change is not None:
                        if pd.Timestamp('now') - self.time_high_power_change > self.heating_time_interval:
                            self.set_low_power()
                            try:
                                self.calculate_thermal_conductivity()
                            except Exception as error:
                                #self.error_output.delete(0, tk.END)
                                #self.error_output.insert(0, f' Error calculating Thermal Conductivity: {error}')
                                print(pd.Timestamp('now').strftime('%X'),
                                      f'Error calculating Thermal Conductivity: {error}')
                            self.time_high_power_change = None  # reset time
                            self.create_new_file = True  # start new file after measurement
                            self.start_idle_mode()

                # mode: autocycle
                elif self.start_autocycle or self.start_autocycle_non_stat:
                    # get target temperatures from gui
                    self.target_temperatures = input_list.values
                    # check if target temperatures were specified
                    if not self.target_temperatures:
                        self.output.delete(0, tk.END)
                        self.output.insert(0, 'No target temperatures specified!')
                        self.start_idle_mode()
                        continue

                    if self.start_autocycle:
                        self.current_ths_mode = 'autocycle'
                    elif self.start_autocycle_non_stat:
                        self.current_ths_mode = 'autocycle_non_stat'

                    # check if a value was skipped
                    if input_list.get_current_value() == self.target_temperatures[self.target_temperatures_counter+1]:
                        self.target_temperatures_counter += 1
                        self.autocycle_phase == 'set_target_temp'

                    if self.autocycle_phase == 'set_target_temp':
                        if self.current_power_mode != 'low':
                            self.set_low_power()
                        # stop condition if cycle is complete
                        if self.target_temperatures_counter > len(self.target_temperatures) - 1:
                            self.output.delete(0, tk.END)
                            self.output.insert(0, 'Autocycle completed!')
                            print(pd.Timestamp('now').strftime('%X'), 'Autocycle completed!')
                            self.start_idle_mode()
                            continue
                        # set new temp to list input, will be changed by GUI_TVAC_PID.py function
                        self.current_target_temp = self.target_temperatures[self.target_temperatures_counter]
                        input_list.mark_value(mark_index=self.target_temperatures_counter)
                        # go to next phase
                        self.autocycle_phase = 'wait_for_stationary'
                        self.time_at_last_stationary_check = pd.Timestamp.now()

                    elif self.autocycle_phase == 'wait_for_stationary':
                        # test if temperature is stationary every 10th of the stationary_time_interval
                        if pd.Timestamp(
                                'now') >= self.time_at_last_stationary_check + self.stationary_time_interval / 10:
                            self.time_at_last_stationary_check = pd.Timestamp('now')
                            # check if stationary and at what mean temperature
                            try:
                                is_stationary, mean_temp = self.is_stationary_old()
                            except Exception as error:
                                print(pd.Timestamp('now').strftime('%X'), f'Failed to check stationary: {error}')
                            if is_stationary:
                                print(pd.Timestamp('now').strftime('%X'), f'Autocycle stationary at: {mean_temp}K')
                                if (self.current_target_temp - self.target_range <= mean_temp and
                                        mean_temp <= self.current_target_temp + self.target_range):
                                    self.autocycle_phase = 'measure'
                                else:
                                    self.output.delete(0, tk.END)
                                    self.output.insert(0, f'Stationary at: {mean_temp} K')
                            else:
                                print(pd.Timestamp('now').strftime('%X'), f'Autocycle not stationary at: {mean_temp}K')

                                # do non stat measurement if not stationary and enough time has passed since last one
                                if self.current_ths_mode == 'autocycle_non_stat':
                                    if pd.Timestamp('now') >= (self.last_measurement_time + 3 * self.heating_time_interval +
                                                               self.time_span_non_stat_measurements):
                                        # only measure non stat if not in proximity to stationary state
                                        if not (self.current_target_temp - 2*self.target_range <= mean_temp and
                                                mean_temp <= self.current_target_temp + 2*self.target_range):
                                            self.autocycle_phase = 'measure_non_stat'

                    elif self.autocycle_phase == 'measure' or self.autocycle_phase == 'measure_non_stat':
                        # initially change power mode to high
                        if self.current_power_mode != 'high':
                            self.last_measurement_time = pd.Timestamp('now')
                            self.set_high_power(self.measure_voltage)
                            self.time_high_power_change = pd.Timestamp('now')
                            self.create_new_file = True  # start new file for measurement
                        # stop measurement after heating_time_interval (adjustable) and calculate heat conductivity
                        elif self.current_power_mode == 'high' and self.time_high_power_change is not None:
                            if pd.Timestamp('now') - self.time_high_power_change > self.heating_time_interval:
                                self.set_low_power()
                                self.time_high_power_change = None  # reset time
                                self.create_new_file = True  # start new file after measurement

                                # calculate thermal conductivity instantly (not possible for non stat)
                                if self.autocycle_phase == 'measure':
                                    try:
                                        thermal_cond, thermal_cond_err, *_ = self.calculate_thermal_conductivity()
                                    except Exception as error:
                                        #self.error_output.delete(0, tk.END)
                                        #self.error_output.insert(0, f'Autocycle: Error calculating '
                                        #                            f'Thermal Conductivity: {error}')
                                        print(pd.Timestamp('now').strftime('%X'),
                                              f'Autocycle: Error calculating Thermal Conductivity: {error}')

                                    print(pd.Timestamp('now').strftime('%X'),
                                          'Autocycle: Checking thermal conductivites for validity')
                                    self.thermal_conductivities_to_check.append((thermal_cond, thermal_cond_err))
                                    # go to next target temp if thermal conds match, measure again at same temp if not
                                    if self.check_thermal_conductivities():
                                        self.thermal_conductivities_to_check = []
                                        self.target_temperatures_counter += 1
                                        print(pd.Timestamp('now').strftime('%X'), 'Targeting next temperature')
                                    # go to first phase again
                                    self.autocycle_phase = 'set_target_temp'

                                # go back to waiting phase until next non stat measurement or stationary state occurs
                                elif self.autocycle_phase == 'measure_non_stat':
                                    self.autocycle_phase = 'wait_for_stationary'

                # mode: autosweep
                elif self.start_autosweep:
                    # temperature changes will be done automatically via GUI_TVAC_PID.py upon starting autosweep
                    # based on THS.temp_gradient specified in GUI and the current TVAC temperature
                    self.current_ths_mode = 'autosweep'

                    if self.autosweep_phase == 'wait':
                        # check if enough time has passed and perform measurement
                        if pd.Timestamp('now') >= (self.last_measurement_time + 3 * self.heating_time_interval +
                                                   self.time_span_non_stat_measurements):
                            self.autosweep_phase = 'measure'

                    # perform measurement
                    if self.autosweep_phase == 'measure':
                        # initially change power mode to high
                        if self.current_power_mode != 'high':
                            self.last_measurement_time = pd.Timestamp('now')
                            self.set_high_power(self.measure_voltage)
                            self.time_high_power_change = pd.Timestamp('now')
                            self.create_new_file = True  # start new file for measurement
                        # stop measurement after heating_time_interval and calculate heat conductivity
                        elif self.current_power_mode == 'high' and self.time_high_power_change is not None:
                            if pd.Timestamp('now') - self.time_high_power_change > self.heating_time_interval:
                                self.set_low_power()
                                self.time_high_power_change = None  # reset time
                                self.create_new_file = True  # start new file after measurement

                                # calculate thermal conductivity instantly (not always possible for non stat)
                                try:
                                    thermal_cond, thermal_cond_err, *_ = self.calculate_thermal_conductivity()
                                except Exception as error:
                                    #self.error_output.delete(0, tk.END)
                                    #self.error_output.insert(0, f'Autocycle: Error calculating '
                                    #                            f'Thermal Conductivity: {error}')
                                    print(pd.Timestamp('now').strftime('%X'),
                                          f'Autosweep: Error calculating Thermal Conductivity: {error}')

                                # go into waiting phase until next measurement is due
                                self.autosweep_phase = 'wait'





    ##############################
    # GUI Functions
    ##############################

    def start_manual_measurement(self):
        if self.running and not self.end:
            self.start_measurement_manually = True
            self.start_autocycle = False
            self.start_autocycle_non_stat = False
            self.start_autosweep = False
            self.start_idle = False

    def start_autocycle_measurement(self):
        if self.running and not self.end:
            self.start_measurement_manually = False
            self.start_autocycle = True
            self.start_autocycle_non_stat = False
            self.start_autosweep = False
            self.autocycle_phase = 'set_target_temp'  # initialize autocycle in phase one
            self.start_idle = False

    def start_autocycle_non_stat_measurement(self):
        if self.running and not self.end:
            self.start_measurement_manually = False
            self.start_autocycle = False
            self.start_autocycle_non_stat = True
            self.start_autosweep = False
            self.autocycle_phase = 'set_target_temp'  # initialize autocycle in phase one
            self.start_idle = False
            self.last_measurement_time = pd.Timestamp('now')  # init time to 'now' to avoid instant measurement

    def start_autosweep_mode(self):
        if self.running and not self.end:
            self.start_measurement_manually = False
            self.start_autocycle = False
            self.start_autocycle_non_stat = False
            self.start_autosweep = True
            self.autocycle_phase = 'set_target_temp'  # initialize autocycle in phase one
            self.start_idle = False
            self.last_measurement_time = pd.Timestamp('now')  # init time to 'now' to avoid instant measurement

    def start_idle_mode(self):
        if self.running and not self.end:
            self.start_measurement_manually = False
            self.start_autocycle = False
            self.start_autocycle_non_stat = False
            self.start_autosweep = False
            self.start_idle = True

    def set_stationary_time(self):
        if self.running and not self.end:
            self.SET_stationary_time = True

    def set_heating_time(self):
        if self.running and not self.end:
            self.SET_heating_time = True

    def set_measure_voltage(self):
        if self.running and not self.end:
            self.SET_measure_voltage = True

    def set_temp_gradient(self):
        if self.running and not self.end:
            self.SET_temp_gradient = True

    def get_temperature(self, voltage=None, current=None):
        # get temperature from resistance fit function and voltage/current readings
        if voltage is None or current is None or current == 0.0:
            return
        resistance = voltage / current
        temperature = self.temperature_fit_func(resistance) + 273.15
        return temperature

    def write_to_file(self, init=False):
        # Creates a file with init. Reads data from digital multimeter and saves it to file.
        if init:
            header = ['time', 'voltage', 'current', 'shunt_voltage', 'temperature']
            with open("Data/" + self.filename + '.txt', "a+") as f:
                f.write(str(header[0]))
                for value in header[1:]:
                    f.write(',')
                    f.write(str(value))
                f.write('\n')
        else:
            time.sleep(0.75)
            # read data from multimeter and save to file
            feedback = self.SDM.get_latest_measurement()
            if feedback is None:
                return
            if self.latest_feedback is not None:
                # check if some time passed since old feedback, continue if not
                if feedback[0] < self.latest_feedback[0] + pd.Timedelta(0.75, 's'):
                    return
            if feedback is not None:
                self.latest_feedback = feedback
                time_value = feedback[0]
                ths_voltage = abs(feedback[3])  # value in mV
                ths_shunt_voltage = abs(feedback[4])

                ths_current = ths_shunt_voltage / self.shunt_resistance
                self.current_temp = self.get_temperature(ths_voltage, ths_current)
                if np.nan in [time_value, ths_voltage, ths_current, ths_shunt_voltage]:
                    print(pd.Timestamp('now').strftime('%X'), 'Invalid device feedback found! Skipping values.')
                    return
                if self.current_temp < 77 or self.current_temp > 600:  # filter out data spikes due to power change
                    print(pd.Timestamp('now').strftime('%X'), 'Invalid device feedback found! Skipping values.')
                    return
                with open("Data/" + self.filename + '.txt', "a+") as f:
                    f.write(str(time_value.strftime('%Y-%m-%d %H:%M:%S')))
                    for value in [ths_voltage, ths_current, ths_shunt_voltage, self.current_temp]:
                        f.write(',')
                        f.write(str(value))
                    f.write('\n')
                self.output.delete(0, tk.END)
                self.output.insert(0, pd.Timestamp('now').strftime('%X') + ' Data saved!')

    ##############################
    # Power supply control
    ##############################

    def set_low_power(self):
        # low power mode for idle
        time.sleep(0.5)
        self.change_power_supply_power(current=0.1, voltage=0.2)

        self.current_power_mode = 'low'

        self.output.delete(0, tk.END)
        self.output.insert(0, 'Power changed to low!')
        time.sleep(1.5)

    def set_high_power(self, voltage):
        # high power mode for measurements
        time.sleep(0.5)
        try:
            new_voltage = voltage
            if new_voltage > 5:
                self.output.delete(0, tk.END)
                self.output.insert(0, 'Voltage input too high! Setting to default value.')
                new_voltage = self.default_voltage
        except ValueError as error:
            self.output.delete(0, tk.END)
            self.output.insert(0, f'Voltage input error. Setting to default value. {error}')
            new_voltage = self.default_voltage
        self.change_power_supply_power(current=1.0, voltage=new_voltage)

        self.current_power_mode = 'high'

        self.output.delete(0, tk.END)
        self.output.insert(0, 'Power changed to high!')
        time.sleep(1.5)

    def start_power_supply(self):
        # open SPD series power supply
        try:
            self.power_supply = self.rm.open_resource('USB0::0xF4EC::0xF4EC::SPD13DCC7R0080::INSTR')
            time.sleep(1)
            self.power_supply.write_termination = '\n'
            self.power_supply.read_termination = '\n'

            self.power_supply.write('CH1:CURRent ' + '0.1')
            time.sleep(0.05)
            self.power_supply.write('CH1:VOLTage ' + '0.2')
            time.sleep(0.5)
            self.power_supply.write('OUTP CH1,ON')
            time.sleep(0.05)
        except Exception as error:
            self.error_output.delete(0, tk.END)
            self.error_output.insert(0, f'THS: Error starting power supply: {error}')
            time.sleep(1)
        return

    def change_power_supply_power(self, current=None, voltage=None):
        # change power output of SPD series power supply
        if current is None or voltage is None:
            return
        if self.power_supply is None:
            print(pd.Timestamp('now').strftime('%X'), 'Restarting THS Power Supply')
            self.start_power_supply()
            time.sleep(1)
        try:
            self.power_supply.write('OUTP CH1,OFF')
            time.sleep(0.05)
            self.power_supply.write('CH1:CURRent ' + str(current))
            time.sleep(0.05)
            self.power_supply.write('CH1:VOLTage ' + str(voltage))
            time.sleep(0.5)
            self.power_supply.write('OUTP CH1,ON')
            time.sleep(0.05)
        except Exception as error:
            self.error_output.delete(0, tk.END)
            self.error_output.insert(0, f'THS: Error changing power: {error}')
            return

    def stop_power_supply(self):
        # stops power supply
        try:
            self.power_supply.write('OUTP CH1,OFF')
            time.sleep(0.05)
            self.power_supply.close()

            self.output.delete(0, tk.END)
            self.output.insert(0, 'Power Supply stopped!')
        except Exception as error:
            print(pd.Timestamp('now').strftime('%X'), f'THS: Error closing power supply: {error}')
            pass

    def stop_THS(self):
        # stops THS system
        self.end = True
        self.stop_power_supply()
        self.running = False
        try:
            self.output.delete(0, tk.END)
            self.output.insert(0, 'THS stopped!')
        except AttributeError:
            pass

    def reset_sdm(self, SDM):
        self.SDM = SDM

    ##############################
    # Calculations for thermal conductivity and autocycle
    ##############################
    def correct_temp_gradient(self, filepaths=None):
        """
        Corrects a temperature gradient during a measurement by fitting the previous (and subsequent) datafiles and
        subtracting the gradient from the measured data.
        Finally, the corrected thermal_conductivity is calculated.
        Multiple plots as well as the corrected data are saved
        """
        # load data from file
        if filepaths is None:
            filepaths = ["Data/" + self.filename + '.txt']
        # read data (if needed, concat from multiple files)
        data_list = []
        filepath = None
        for filepath in filepaths:
            if filepath.endswith('THS.txt'):
                df = pd.read_csv(filepath, header=0)
                df = df.dropna()
                if df.shape[0] == 0:
                    continue
                df['time'] = pd.to_datetime(df['time'].values)
                data_list.append(df)
                dir_path = os.path.dirname(filepath)

        try:
            data = pd.concat(data_list)
            data = data.dropna()
        except:
            self.output.delete(0, tk.END)
            self.output.insert(0, 'Calculating thermal conductivity: No files selected!')
            return

        data = data.sort_values(by='time')
        data = data.reset_index(drop=True)

        # find and load data right before and after the measurement
        all_files = [dir_path + "\\" + file for file in sorted(os.listdir(dir_path)) if
                     (file.endswith('THS.txt') & (not file.endswith('_corrected_THS.txt')))]
        file_idx = all_files.index(filepath)
        file_paths_before = all_files[:file_idx]
        data_before = []
        for file_path_before in file_paths_before:
            data_before_single = pd.read_csv(file_path_before, header=0).dropna()
            if not data_before_single.empty:
                data_before.append(data_before_single)
        data_before = pd.concat(data_before)
        data_before['time'] = pd.to_datetime(data_before['time'])
        data_before.sort_values(by='time')
        data_before = data_before[data_before['current'] <= 0.005]
        try:
            file_paths_after = all_files[file_idx+1:]
            data_after = []
            for file_path_after in file_paths_after:
                data_after_single = pd.read_csv(file_path_after, header=0).dropna()
                if not data_after_single.empty:
                    data_after.append(data_after_single)
            data_after = pd.concat(data_after)
            data_after['time'] = pd.to_datetime(data_after['time'])
            data_after.sort_values(by='time')
        except Exception as error:
            data_after = data.copy().iloc[0:0]  # empty data frame with same header
            print(error)

        # check if temperature was stationary (with different time possibilities), only do correction if not stationary
        is_stationary, _ = self.is_stationary_old(data=data_before)
        is_stationary_short, _ = self.is_stationary_old(data=data_before, stationary_time_interval=pd.Timedelta(1, 'h'))
        is_stationary_long, _ = self.is_stationary_old(data=data_before, stationary_time_interval=pd.Timedelta(1, 'h'))
        if is_stationary or is_stationary_short or is_stationary_long:
            return filepaths  # return initial filepath without correction

        data_combined = pd.concat([data_before, data, data_after])

        # determine time values to start, interrupt and end the fit (relative to heating_time_interval)
        fit_start = data_before['time'].iloc[0]
        measurement_start = data_before['time'].iloc[-1]
        measurement_end = data['time'].iloc[-1]
        fit_restart = data['time'].iloc[-1] + 3 * self.heating_time_interval
        if data_after.shape[0] != 0:
            if data_after['time'].iloc[-1] >= fit_restart:
                fit_end = data_after['time'].iloc[-1]
            else:
                fit_end = data['time'].iloc[-1]
        else:
            fit_end = data['time'].iloc[-1]

        def fit_linear(x, a, b):
            return a + b * x

        def fit_polynomial(x, a, b, c, d, e, f):
            # return a + b*x + c*x**3  # small polynom
            return a + b * x ** 1 + c * x ** 2 + d * x ** 3 + e * x ** 4 + f * x ** 5  # polynomial
        fit_data = []
        for kk in range(2):  # loop to try linear and polynomial fit
            if kk == 0:
                print('Skipping linear fit')
                continue # temporary - change later
            is_fit_bad = True
            for ii in range(15):  # loop to allow more fits (shifting start value)
                if not is_fit_bad:  # break loop if previous fit was good enough
                    break
                if kk == 0:
                    fit_func = fit_linear
                    fit_label = 'Linear Fit'
                    # only use data before measurement for linear fit, change fit_start with ii loop to get best fit
                    data_fit = data_combined[((data_combined['time'] >= fit_start) &
                                              (data_combined['time'] <= measurement_start))].copy()
                elif kk == 1:
                    fit_label = 'Polynomial Fit'
                    fit_func = fit_polynomial
                    # also use data after measurement for polynomial fit
                    data_fit = data_combined[((data_combined['time'] >= fit_start) &
                                              (data_combined['time'] <= measurement_start)) |
                                             ((data_combined['time'] >= fit_restart) &
                                              (data_combined['time'] <= fit_end))].copy()
                data_fit['seconds'] = (data_fit['time'] - data_fit['time'].iloc[0]).dt.total_seconds()

                # fitting function and fit
                fit_params, fit_pcov = sc.optimize.curve_fit(fit_func, xdata=data_fit['seconds'], ydata=data_fit['temperature'])

                # calculate data for plot
                fit_xdata = pd.date_range(start=data_fit['time'].iloc[0], end=max(data_fit['time'].iloc[-1], measurement_end), freq='s')
                fit_xdata_seconds = (fit_xdata - fit_xdata[0]).total_seconds()
                fit_ydata = fit_func(fit_xdata_seconds, *fit_params)
                data_fit['deviation'] = data_fit['temperature'] - fit_func(data_fit['seconds'], *fit_params)

                # check if fit is good enough (95% in 0.2K environment)
                data_fit['temperature_okay'] = ((data_fit['deviation'] <= self.max_temp_deviation_gradient) &
                                                (data_fit['deviation'] >= - self.max_temp_deviation_gradient))
                is_fit_bad = (data_fit['temperature_okay'].sum() < self.min_ratio_in_interval_gradient * data_fit.shape[0]
                              or (fit_pcov is None) or (data_fit['deviation'].max() >= 2*self.max_temp_deviation_gradient))
                # break if fit is good
                if not is_fit_bad:
                    break
                else:
                    if ii <= 5:  # tighten limits to find better fit (alternating between start and end value)
                        if ii%2 == 0:
                            new_fit_start = fit_start + self.heating_time_interval
                            if measurement_start-new_fit_start >= self.time_span_non_stat_measurements:
                                fit_start = new_fit_start
                        else:
                            new_fit_end = fit_end - self.heating_time_interval
                            if new_fit_end - fit_restart >= self.time_span_non_stat_measurements:
                                if data_after.shape[0] != 0:  # check if there is any data
                                    if data_after['time'].iloc[-1] >= fit_restart:
                                        fit_end = new_fit_end
                    elif ii == 5:
                        fit_start = measurement_start - self.time_span_non_stat_measurements
                        fit_end = fit_restart + self.time_span_non_stat_measurements
                    elif ii > 5 and ii < 10:  # if too much data exists (before or after), try to go from different direction
                        if ii%2 == 0:
                            new_fit_start = fit_start + self.heating_time_interval
                            if measurement_start - new_fit_start >= 3 * self.heating_time_interval:
                                fit_start = new_fit_start
                        else:
                            new_fit_end = fit_end - self.heating_time_interval
                            if new_fit_end - fit_restart >= 3 * self.heating_time_interval:
                                if data_after.shape[0] != 0:  # check if there is any data
                                    if data_after['time'].iloc[-1] >= fit_restart:
                                        fit_end = new_fit_end
                    elif ii == 10:
                        fit_start = measurement_start - 2 * self.heating_time_interval
                        fit_end = fit_restart + 2 * self.heating_time_interval
                    elif ii > 10:  # if nothing works, shorten start time to few hours before measurement
                        if ii % 2 == 0:
                            fit_start -= self.heating_time_interval
                        else:
                            fit_end += self.heating_time_interval

            if is_fit_bad and kk == 0:  # continue to polynomial fit if fit is bad
                continue
            else:
                break  # break here if linear fit is good enough
        print(ii, fit_restart, fit_end, is_fit_bad)
        if not is_fit_bad:
            starting_temp = data_combined[data_combined['time'] <= measurement_start]['temperature'].iloc[-5:-1].mean()
            # correct the original temperature values with the new fit
            data_corrected = data.copy()
            data_corrected['fit_seconds'] = (data_corrected['time'] - data_fit['time'].iloc[0]).dt.total_seconds()
            data_corrected['temperature_old'] = data_corrected['temperature']
            data_corrected['fit_ydata'] = fit_func(data_corrected['fit_seconds'], *fit_params)
            data_corrected['temperature'] = ((data_corrected['temperature'] - data_corrected['fit_ydata']) + starting_temp)
        else:
            self.error_output.delete(0, tk.END)
            self.error_output.insert(0, f'THS: Temperature deviation from fit too large for correction. '
                                        f'{data_fit.temperature_okay.sum() / data_fit.shape[0]:.2f}% in '
                                        f'{self.max_temp_deviation_gradient}K interval. '
                                        f'Max dev. {data_fit.deviation.max():.2f}K of 2 * {self.max_temp_deviation_gradient}K')
            plot_without_correction = True
            print(ii)

        # save corrected data as .txt
        filepath_corrected = filepath.removesuffix("_THS.txt") + "_corrected_THS.txt"
        if not is_fit_bad:
            data_corrected.to_csv(filepath_corrected, index=False)

        # plot figure with fit and corrected data
        fig = plt.figure()
        ax = fig.subplots()
        ax.set_xlabel('Time')
        ax.set_ylabel('Temperature')

        ax.plot(data_combined['time'], data_combined['temperature'], label='THS Temperature', color='blue')
        ax.plot(fit_xdata, fit_ydata, color='red', label=fit_label, linestyle='dashed')
        if not is_fit_bad:
            ax.plot(data_corrected['time'], data_corrected['temperature'], color='green', label='Corrected Temperature')
        print(fit_label)
        date_format = DateFormatter("%H:%M")
        ax.xaxis.set_major_formatter(date_format)
        hours = (data_combined['time'].iloc[-1] - data_combined['time'].iloc[0]).total_seconds() / 3600
        hoursteps = int((hours - 1) // 9 + 1)
        locator = HourLocator(interval=hoursteps)
        ax.xaxis.set_major_locator(locator)
        xlim_upper = max(data_fit['time'].iloc[-1],
                         fit_restart + 3 * self.heating_time_interval) if data_after.shape[0] == 0 else fit_restart
        ax.set_xlim(data_fit['time'].iloc[0], xlim_upper)
        if not is_fit_bad:
            y_upper = max(max(fit_ydata.max() + 1, data_corrected['temperature'].max() + 1),
                          data_corrected['temperature_old'].max() + 1)
            ax.set_ylim(fit_ydata.min() - 1, y_upper)
        print(data_fit['time'].iloc[0], xlim_upper)
        ax.legend()
        ax.grid(axis='both', linestyle='dashed', linewidth=0.5, alpha=0.5)
        filepath_image = (filepath_corrected.removesuffix(".txt") + "_fit.png").replace('\\', '/')
        fig.savefig(filepath_image, dpi=300, bbox_inches="tight")
        # Plot difference of fit and original data
        fig2 = plt.figure()
        ax2 = fig2.subplots()
        ax2.set_xlabel('Time')
        ax2.set_ylabel('Temperature deviation from fit (K)')

        ax2.set_xlim(data_fit['time'].iloc[0], xlim_upper)
        ax2.set_ylim(-0.5, 0.5)

        ax2.plot(data_fit['time'], data_fit['deviation'], color='black')

        ax2.vlines(x=measurement_start, ymin=-1, ymax=1, label='Measurement', color='black', linestyle='dashed')
        ax2.vlines(x=fit_restart, ymin=-1, ymax=1, color='black', linestyle='dashed')

        date_format = DateFormatter("%H:%M")
        ax2.xaxis.set_major_formatter(date_format)
        locator = HourLocator(interval=hoursteps)
        ax2.xaxis.set_major_locator(locator)

        ax2.grid(axis='both', linestyle='dashed', linewidth=0.5, alpha=0.5)
        ax2.legend()
        filepath_image = (filepath_corrected.removesuffix(".txt") + "_diff.png").replace('\\', '/')
        fig2.tight_layout()
        fig2.savefig(filepath_image, dpi=300, bbox_inches="tight")

        if is_fit_bad:
            return None
        else:
            return [filepath_corrected]

    def calculate_thermal_conductivity(self, filepaths=None):
        """
        Calculate heat conductivity based on Gustafsson (1979), Hammerschmidt and Sabuga (1999)
        """
        if filepaths is None:
            filepaths = ["Data/" + self.filename + '.txt']
        # read data (if needed, concat from multiple files)
        data_list = []
        for filepath in filepaths:
            if filepath.endswith('THS.txt'):
                df = pd.read_csv(filepath, header=0)
                df = df.dropna()
                if df.shape[0] == 0:
                    continue
                df['time'] = pd.to_datetime(df['time'].values)
                data_list.append(df)
        try:
            data = pd.concat(data_list)
            data = data.sort_values(by='time')
            data = data.reset_index(drop=True)
        except:
            self.output.delete(0, tk.END)
            self.output.insert(0, 'Calculating thermal conductivity: No files selected!')
            return

        # select only values where power was high
        data = data[data['current'] > 0.005]
        start_temp = data['temperature'].iloc[0]
        df_result = self.calculate_thermal_cond_automatically(data, filepath, start_temp, min_linear_time=100)
        row_dict = df_result.iloc[0].to_dict()
        thermal_conductivity, thermal_conductivity_error, thermal_cond_fit_err, thermal_cond_linearmodel_err, \
            thermal_diffusivity, thermal_diffusivity_error, thermal_diff_fit_err, thermal_diff_linearmodel_err, \
            temp, temp_err, tau_min, tau_max, tau_max_limit, fit_start, fit_end, \
            m, m_err, n, n_err, idx, datetime, is_corrected = row_dict.values()

        return (thermal_conductivity, thermal_conductivity_error, thermal_diffusivity, thermal_diffusivity_error,
                temp, temp_err, tau_min, tau_max, datetime, is_corrected)

    def check_thermal_conductivities(self):
        """
        Checks wether two (or more) calculated thermal conductivites at the same temperature
        are within each others error interval to test if a measurement was valid.
        Returns True if intervals overlap at least half of the time, or if only one value was measured.
        Return False otherwise.
        """
        # continue with autocycle if only one value exists
        cond_num = len(self.thermal_conductivities_to_check)
        if cond_num == 1:
            return False

        # initialize lists for error intervals
        lower_boundaries = []
        upper_boundaries = []
        for thermal_cond, thermal_cond_err in self.thermal_conductivities_to_check:
            lower_boundaries.append(thermal_cond - thermal_cond_err)
            upper_boundaries.append(thermal_cond + thermal_cond_err)

        valid_cond_counter = 0  # count measurements where at least half of other intervals overlap the error interval
        # check if each measurement has some overlap with the other error intervals
        for ii, (thermal_cond, thermal_cond_err) in enumerate(self.thermal_conductivities_to_check):
            in_bounds_counter = 0  # counting overlaps for a single measurement
            for jj, (lower_boundary, upper_boundary) in enumerate(zip(lower_boundaries, upper_boundaries)):
                if ii == jj:
                    continue
                # check if error interval of measured value lies within error intervals of other values
                if lower_boundary <= lower_boundaries[ii] <= upper_boundary:
                    in_bounds_counter += 1
                    continue
                if lower_boundary <= upper_boundaries[ii] <= upper_boundary:
                    in_bounds_counter += 1
                    continue
            if in_bounds_counter >= 1 / 2 * cond_num:
                valid_cond_counter += 1

        if valid_cond_counter >= 1 / 2 * cond_num:
            return True
        else:
            return False

    def is_stationary_old(self, data=None, stationary_time_interval=None):
        """
        Checks if latest temperature data is stationary. Also returns mean temperature of last time interval.
        """

        def check_temperature(data, max_temp_deviation, min_ratio_in_interval):
            """
            checks if temperature values of data exceed a maximum deviation.
            min_ratio_in_interval allows for some values to lie outside (data spikes, small fluctuations)
            """
            # check if temperature is stable around the current mean value
            temperature_okay = False
            mean_temp = data['temperature'].mean()
            data['temperature_okay'] = (data['temperature'] <= mean_temp + max_temp_deviation) & (
                        data['temperature'] >= mean_temp - max_temp_deviation)
            if data['temperature_okay'].sum() >= min_ratio_in_interval * data.shape[0]:
                temperature_okay = True
            #print(data['temperature_okay'].sum()/data.shape[0])
            return temperature_okay, mean_temp

        def linear_regression(x, y):
            """
            calculates a linear regression of x and y with standard errors of slope and intercept
            """
            x = np.array(x)
            y = np.array(y)
            x = x.reshape(-1, 1)  # Reshape x to a 2D array (n_samples, n_features)
            # Create a LinearRegression model and fit the data
            model = LinearRegression()
            model.fit(x, y)
            # Get the coefficients (slope and intercept) and their standard errors
            slope = model.coef_[0]
            intercept = model.intercept_
            # Calculate the residuals (error of the fit for each value)
            y_pred = model.predict(x)
            residuals = y - y_pred
            # Calculate the standard errors of the coefficients
            n = len(x)
            degrees_of_freedom = n - 2  # Two degrees of freedom for slope and intercept
            mse_resid = np.sum(residuals ** 2) / degrees_of_freedom  # mean squared error
            slope_error = np.sqrt(mse_resid / np.sum((x - np.mean(x)) ** 2))  # standard error of slope
            intercept_error = np.sqrt(
                mse_resid * (1 / n + (np.mean(x) ** 2) / np.sum((x - np.mean(x)) ** 2)))  # standard error of intercept
            return slope, intercept, slope_error, intercept_error

        def check_slope(data, mean_temp, max_temp_deviation, min_time_interval):
            """
            checks if the slope as calculated from a linear regression of the given data exceeds the
            max temperature deviation within the next time interval.
            """
            slope_okay = False
            # check if current slope is fine
            min_time_interval_seconds = min_time_interval.total_seconds()  # get interval in seconds

            slope, intercept, slope_err, intercept_err = linear_regression(data['seconds'], data['temperature'])
            # check slope starting from center of data at mean temp up to the end of a second interval
            expected_temp_max = mean_temp + (slope - slope_err) * 1.5 * min_time_interval_seconds
            expected_temp_min = mean_temp + (slope + slope_err) * 1.5 * min_time_interval_seconds
            if ((expected_temp_max <= mean_temp + max_temp_deviation) &
                    (expected_temp_max >= mean_temp - max_temp_deviation) &
                    (expected_temp_min <= mean_temp + max_temp_deviation) &
                    (expected_temp_min >= mean_temp - max_temp_deviation)):
                slope_okay = True
            return slope_okay, slope, intercept, slope_err, intercept_err
        # check if different statioanry time interval was given
        if stationary_time_interval is not None:
            self.stationary_time_interval = stationary_time_interval
        # read data
        if data is None:
            data = pd.read_csv("Data/" + self.filename + '.txt', header=0)
            data = data.dropna()
            data['time'] = pd.to_datetime(data['time'].values)
        else:
            data = data.copy()
        # return if not enough data is available
        if data['time'].iloc[-1] <= data['time'].iloc[0] + self.stationary_time_interval:
            print(pd.Timestamp('now').strftime('%X'), 'THS.is_stationary: waiting for more data')
            return False, None
        is_stationary = False  # initialize
        # select only values within the latest time interval
        data = data[data['time'] >= data['time'].iloc[-1] - self.stationary_time_interval]
        data['seconds'] = (data['time'] - data['time'].iloc[0]).dt.total_seconds()
        data = data.set_index('time')
        data = data.dropna()
        # check if conditions are met for temperature and slope
        temperature_within_limits, mean_temp = check_temperature(data, self.max_temp_deviation,
                                                                 self.min_ratio_in_interval)
        slope_small_enough, slope, intercept, slope_err, intercept_err = check_slope(data, mean_temp,
                                                                                     self.max_temp_deviation,
                                                                                     self.stationary_time_interval)
        #print(temperature_within_limits, mean_temp, slope_small_enough, slope)
        if temperature_within_limits & slope_small_enough:
            is_stationary = True

        return is_stationary, mean_temp

    def is_stationary(self, x_values, y_values, x_interval_size, max_deviation, min_ratio_in_interval=0.95):
        """
        Checks if latest temperature data is stationary. Also returns mean temperature of last time interval.
        """

        def check_in_interval(y_values, max_deviation, min_ratio_in_interval):
            """
            checks if temperature values of data exceed a maximum deviation.
            min_ratio_in_interval allows for some values to lie outside (data spikes, small fluctuations)
            """
            # check if temperature is stable around the current mean value
            values_are_in_interval = False
            mean = y_values.mean()
            value_idxs_in_interval = (y_values <= mean + max_deviation) & (
                    y_values >= mean - max_deviation)
            if value_idxs_in_interval.sum() >= min_ratio_in_interval * y_values.size:
                values_are_in_interval = True
            # print(data['temperature_okay'].sum()/data.shape[0])
            return values_are_in_interval, mean

        def linear_regression(x, y):
            """
            calculates a linear regression of x and y with standard errors of slope and intercept
            """
            x = np.array(x)
            y = np.array(y)
            x = x.reshape(-1, 1)  # Reshape x to a 2D array (n_samples, n_features)
            # Create a LinearRegression model and fit the data
            model = LinearRegression()
            model.fit(x, y)
            # Get the coefficients (slope and intercept) and their standard errors
            slope = model.coef_[0]
            intercept = model.intercept_
            # Calculate the residuals (error of the fit for each value)
            y_pred = model.predict(x)
            residuals = y - y_pred
            # Calculate the standard errors of the coefficients
            n = len(x)
            degrees_of_freedom = n - 2  # Two degrees of freedom for slope and intercept
            mse_resid = np.sum(residuals ** 2) / degrees_of_freedom  # mean squared error
            slope_error = np.sqrt(mse_resid / np.sum((x - np.mean(x)) ** 2))  # standard error of slope
            intercept_error = np.sqrt(
                mse_resid * (1 / n + (np.mean(x) ** 2) / np.sum((x - np.mean(x)) ** 2)))  # standard error of intercept
            return slope, intercept, slope_error, intercept_error

        def check_slope(x_values, y_values, mean, max_deviation, x_interval_size):
            """
            checks if the slope as calculated from a linear regression of the given data exceeds the
            max temperature deviation within the next time interval.
            """
            slope_okay = False
            # check if current slope is fine

            slope, intercept, slope_err, intercept_err = linear_regression(x_values, y_values)
            # check slope starting from center of data at mean temp up to the end of a second interval
            expected_max = mean + (slope - slope_err) * 1.5 * x_interval_size
            expected_min = mean + (slope + slope_err) * 1.5 * x_interval_size
            if ((expected_max <= mean + max_deviation) &
                    (expected_max >= mean - max_deviation) &
                    (expected_min <= mean + max_deviation) &
                    (expected_min >= mean - max_deviation)):
                slope_okay = True
            return slope_okay, slope, intercept, slope_err, intercept_err

        is_stationary = False
        # check if conditions are met for temperature and slope
        temperature_within_limits, mean = check_in_interval(y_values, max_deviation, min_ratio_in_interval)
        slope_small_enough, slope, intercept, slope_err, intercept_err = check_slope(x_values, y_values, mean,
                                                                                     max_deviation,
                                                                                     x_interval_size)
        # print(temperature_within_limits, mean, slope_small_enough, slope)
        if temperature_within_limits & slope_small_enough:
            is_stationary = True

        return is_stationary, mean


    def fit_func_poly_5(self, x, a, b, c, d, e, f):
        return a + b*x + c*x**2 + d*x**3 + e*x**4 + f*x**5

    def fit_func_linear(self, x, a, b):
        return a + b*x

    def fit_func_newton(self, x, T_i, T_eq, h):
        return T_eq + (T_i - T_eq) * (1-np.exp(-h * x))

    def fit_func_newton_err(self, x, params, params_err):
        T_i, T_eq, h = params
        T_i_err, T_eq_err, h_err = params_err
        return np.sqrt((T_eq_err * (1 - (1 - np.exp(-h * x))))**2 + (T_i_err * (1 - np.exp(-h * x)))**2 +
                       (h_err * (T_i - T_eq) * h * np.exp(-h * x))**2)

    def calculate_fit_error(self, y_true, y_pred):
        mask = ~np.isnan(y_true) & ~np.isnan(y_pred)
        y_true_filtered = y_true[mask]
        y_pred_filtered = y_pred[mask]
        return np.sqrt(np.mean((y_true_filtered - y_pred_filtered)**2))

    def find_best_fit_interval(self, x, y, fit_func, end_initial, step_size, seconds_to_block_after_m):
        # finds best fit for given x and y by varying start and end values
        best_error = float('inf')
        best_params, best_params_err = None, None
        best_start, best_end = None, None
        if fit_func == self.fit_func_linear:
            p0 = [y[0], 1E-5]
            bounds = ([0, -np.inf], [np.inf, np.inf])
        elif fit_func == self.fit_func_poly_5:
            p0 = [y[x == end_initial], 1, 1, 1, 1, 1]
            bounds = ([0, -np.inf, -np.inf, -np.inf, -np.inf, -np.inf], [np.inf]*6)
        elif fit_func == self.fit_func_newton:
            p0 = [y[0], y[-1], 1E-4]
            bounds = ([0, 0, 1E-6], [np.inf, np.inf, 1E-3])

        def fit_and_calculate_error(start, end):
            # check if interval is large enough and end is not within measurement or shortly after
            if end-start < 6*step_size or ((end > end_initial) & (end < end_initial + seconds_to_block_after_m)):
                return None, None, float('inf'), start, end
            x_subset = x[(x >= start) & (x <= end)]
            y_subset = y[(x >= start) & (x <= end)]
            try:
                popt, pcov = sc.optimize.curve_fit(fit_func, x_subset, y_subset, p0=p0, bounds=bounds)
                y_fit_subset = fit_func(x_subset, *popt)
                err = self.calculate_fit_error(y_subset, y_fit_subset)
                if np.abs(err).max() > 0.5:  # max allowed error
                    return None, None, float('inf'), start, end
            except RuntimeError as error:
                return None, None, float('inf'), start, end
            except ValueError as error:
                return None, None, float('inf'), start, end

            return popt, pcov, err, start, end

        # Iterate over possible start and end values, parallelize the fitting
        num_cores = multiprocessing.cpu_count()
        cpu_usage = psutil.cpu_percent(interval=1)
        n_jobs = max(1, num_cores-2) if cpu_usage < 50 else max(1, num_cores-4)
        results = Parallel(n_jobs=n_jobs)(
            delayed(fit_and_calculate_error)(start, end)
            for start in range(end_initial - step_size, int(min(x)), -step_size)
            for end in range(end_initial, int(max(x)), step_size))
        # choose best fit via minimal error (RMSE)
        for popt, pcov, err, start, end in results:
            if err < best_error:
                best_error = err
                best_params = popt
                best_params_err = np.sqrt(np.diag(pcov)) if pcov is not None else None
                best_start, best_end = start, end
        return best_params, best_params_err, best_start, best_end, best_error

    def find_best_fit(self, x, y, fit_func_list, end_initial, step_size, seconds_to_block_after_m):
        params_list, params_err_list, start_list, end_list, error_list = [], [], [], [], []
        for fit_func in fit_func_list:
            params, params_err, start, end, err = self.find_best_fit_interval(x, y, fit_func, end_initial, step_size,
                                                                              seconds_to_block_after_m)
            params_list.append(params)
            params_err_list.append(params_err)
            start_list.append(start)
            end_list.append(end)
            error_list.append(err)

        idx_min = np.argmin(error_list)
        return (fit_func_list[idx_min], params_list[idx_min], params_err_list[idx_min],
                start_list[idx_min], end_list[idx_min], error_list[idx_min])

    def correct_temp_gradient_automatically(self, data_m, data_b, data_a, path_file_m, start_temp, re_correct_data=False):
        mpl.use('Agg')
        path_file_m_corr = path_file_m.replace('_THS.txt', '_corrected_THS.txt')
        if re_correct_data:  # remove all corrected data to do correction again
            path_dir = os.path.dirname(path_file_m)
            for filename in os.listdir(path_dir):
                path_file = os.path.join(path_dir, filename)
                if '_corrected' in filename:
                    os.remove(path_file)
        else:  # return already existent corrected data or continue if non exists
            if os.path.exists(path_file_m_corr):
                data = pd.read_csv(path_file_m_corr, header=0)
                data['time'] = pd.to_datetime(data['time'])
                return data

        data_non_m = pd.concat([data_b, data_a])
        heating_time_interval = data_m['time'].iloc[-1] - data_m['time'].iloc[0]

        # find best fit by varying start/end and minimizing mean squared error
        if data_a.empty or data_a['time'].iloc[-1] < data_m['time'].iloc[-1] + 3 * heating_time_interval:
            fit_func_list = [self.fit_func_newton, self.fit_func_linear]
        else:
            fit_func_list = [self.fit_func_poly_5, self.fit_func_linear]
        fit_earliest_end_time = int(data_b['seconds_combined'].iloc[-1])  # fit at least up to start of measurement

        step_size = heating_time_interval.total_seconds()/3
        fit_func, fit_params, fit_params_err, fit_start, fit_end, fit_error = (
            self.find_best_fit(data_non_m['seconds_combined'].values, data_non_m['temperature'].values, fit_func_list,
                               end_initial=fit_earliest_end_time, step_size=step_size,
                               seconds_to_block_after_m=3*heating_time_interval.total_seconds()))

        fit_err_lim = 0.2
        if fit_error < fit_err_lim:

            if fit_func == self.fit_func_linear:
                fit_label = 'Linear'
                data_m = data_m.assign(temperature_corr_err=
                                       np.sqrt(np.sum([(data_m['seconds_combined']**ii * p_err)**2
                                                       for ii, p_err in enumerate(fit_params_err)])))
            elif fit_func == self.fit_func_poly_5:
                fit_label = 'Polynomial (5th)'
                data_m = data_m.assign(temperature_corr_err=
                                       np.sqrt(np.sum([(data_m['seconds_combined'] ** ii * p_err) ** 2
                                                       for ii, p_err in enumerate(fit_params_err)])))
            elif fit_func == self.fit_func_newton:
                fit_label = 'Newton'
                data_m = data_m.assign(temperature_corr_err=
                                       self.fit_func_newton_err(data_m['seconds_combined'], fit_params, fit_params_err))

            # correct temperature with fit and save to file
            fit_m = fit_func(data_m['seconds_combined'], *fit_params)
            data_to_fit = data_non_m[(data_non_m['seconds_combined'] > fit_start) &
                                     (data_non_m['seconds_combined'] < fit_end)]
            fit_non_m = fit_func(data_to_fit['seconds_combined'], *fit_params)
            data_m = data_m.assign(temperature_uncorr = data_m['temperature'],
                                   temperature = data_m['temperature'] - fit_m + start_temp)
            data_m.to_csv(path_file_m_corr, index=False)


        # plot data (with corrected version))
        fig_corr, ax_corr = plt.subplots()
        ax_corr.plot(data_b['time'], data_b['temperature'], color='blue')
        ax_corr.plot(data_a['time'], data_a['temperature'], color='blue')
        # plot fit (only if fit wasn't bad)
        if fit_error < fit_err_lim:
            ax_corr.plot(data_m['time'], data_m['temperature_uncorr'], color='blue', label='THS Temperature')

            ax_corr.plot(data_to_fit['time'], fit_non_m, linestyle='dashed', color='red',
                         label=f'{fit_label} Fit')
            ax_corr.plot(data_m['time'], fit_m, linestyle='dashed', color='red', alpha=0.25)
            ylims = (min(fit_non_m.min(), data_m['temperature'].min(), data_m['temperature_uncorr'].min()),
                     max(fit_non_m.max(), data_m['temperature'].max(), data_m['temperature_uncorr'].max()))
            # plot corrected data
            ax_corr.plot(data_m['time'], data_m['temperature'], color='green', linestyle='dotted',
                         label='Corrected Temperature')
        else:
            ax_corr.plot(data_m['time'], data_m['temperature'], color='blue', label='THS Temperature')
            ylims = (data_m['temperature'].min() -  1, data_m['temperature'].max() + 1)

        ax_corr.set_ylim(ylims)


        ax_corr.set_xlabel('Time')
        ax_corr.set_ylabel('Temperature (K)')

        locator = mdates.AutoDateLocator(minticks=3, maxticks=9)
        formatter = mdates.ConciseDateFormatter(locator)
        ax_corr.xaxis.set_major_locator(locator)
        ax_corr.xaxis.set_major_formatter(formatter)

        ax_corr.legend(loc="best")
        ax_corr.grid(axis='both', linestyle='dashed', linewidth=0.5)

        path_fig_corr = path_file_m_corr.replace('.txt', '_fit.png')
        fig_corr.savefig(path_fig_corr, bbox_inches='tight', dpi=300)

        if fit_error < fit_err_lim:
            fig_corr_dev, ax_corr_dev = plt.subplots()
            ax_corr_dev.set_xlabel('Time')
            ax_corr_dev.set_ylabel('Temperature Difference from Fit (K)')
            ax_corr_dev.set_ylim(-0.5, 0.5)
            ax_corr_dev.set_xlim(ax_corr.get_xlim())
            ax_corr_dev.xaxis.set_major_locator(locator)
            ax_corr_dev.xaxis.set_major_formatter(formatter)

            ax_corr_dev.plot(data_to_fit['time'], fit_non_m - data_to_fit['temperature'], color='black')
            ax_corr_dev.grid(axis='both', linestyle='dashed', linewidth=0.5)

            path_fig_corr_dev = path_file_m_corr.replace('.txt', '_fit_dev.png')
            fig_corr_dev.savefig(path_fig_corr_dev, bbox_inches='tight', dpi=300)
            return data_m
        else:
            return None

    def correct_temp_gradient_manually(self, data_m, data_b, data_a, path_file_m, start_temp, re_correct_data=False):
        mpl.use('TkAgg')  # for interactive plots
        plt.close('all')
        path_file_m_corr = path_file_m.replace('_THS.txt', '_corrected_THS.txt')
        if re_correct_data:  # remove all corrected data to do correction again
            path_dir = os.path.dirname(path_file_m)
            for filename in os.listdir(path_dir):
                path_file = os.path.join(path_dir, filename)
                if '_corrected' in filename:
                    os.remove(path_file)
        else:  # return corrected data if already existent
            #print(os.path.exists(path_file_m_corr), path_file_m_corr)
            if os.path.exists(path_file_m_corr):
                data = pd.read_csv(path_file_m_corr, header=0)
                data['time'] = pd.to_datetime(data['time'])
                return data
        data_combined = pd.concat([data_b, data_m, data_a])
        data_non_m = pd.concat([data_b, data_a])
        heating_time_interval = data_m['time'].iloc[-1] - data_m['time'].iloc[0]

        # possible fit functions
        selected_limits = []
        line_fit, line_fit_m, line_corr, line_uncorr = None, None, None, None
        def get_xlims(data_before, data_m, data_a):
            if data_a.empty or data_a['time'].iloc[-1] < data_m['time'].iloc[-1] + 3 * heating_time_interval:
                upper_limit = data_m['time'].iloc[-1] + 3 * heating_time_interval
            else:
                upper_limit = data_a['time'].iloc[-1]
            lower_limit = data_before['time'].iloc[0]
            return [lower_limit, upper_limit]

        def get_ylims(data_before, data_m, data_a):
            x_lims = get_xlims(data_before, data_m, data_a)

            def cond(data_condition, xlims=x_lims):
                lower_limit = selected_limits[-2] if selected_limits else x_lims[0]
                upper_limit = selected_limits[-1] if selected_limits else x_lims[1]
                return ((data_condition['time'] >= lower_limit) & (data_condition['time'] <= upper_limit))

            y_lims = (min(data_before[cond(data_before)]['temperature'].min(),
                          min(data_m[cond(data_m)]['temperature'].min(),
                              data_a[cond(data_a)]['temperature'].min())) - 1,
                      max(data_before[cond(data_before)]['temperature'].max(),
                          max(data_m[cond(data_m)]['temperature'].max(),
                              data_a[cond(data_a)]['temperature'].max())) + 1)
            return y_lims

        limits_fit = get_xlims(data_b, data_m, data_a)

        def on_pick(event):
            x, y = event.artist.get_data()
            x_date = x[event.ind[0]]
            selected_limits.append(x_date)
            print('Slected:', x_date)

        def save_figure(event, fig_element, path, axes_to_remove=None):
            if axes_to_remove is not None:
                for ax_element in axes_to_remove:
                    for child in ax_element.get_children():
                        child.set_visible(False)
                    ax_element.set_visible(False)
            print('saving figure')
            fig_element.savefig(path, bbox_inches='tight', dpi=300)

        def set_limits(event):
            if len(selected_limits) < 2:
                print('Not enough limits selected')
                return
            lower_limit = selected_limits[-2] if selected_limits else data_b['time'].iloc[0]
            upper_limit = selected_limits[-1] if selected_limits else data_a['time'].iloc[-1]
            if upper_limit <= data_m['time'].iloc[-1] + 3 * heating_time_interval:
                upper_limit = data_m['time'].iloc[-1] + 3 * heating_time_interval
            print(lower_limit, upper_limit)
            # Clear the selected points list and update the plot
            ax_corr.set_xlim(lower_limit, upper_limit)
            ax_corr.set_ylim(get_ylims(data_b, data_m, data_a))

            locator = mdates.AutoDateLocator(minticks=3, maxticks=9)
            formatter = mdates.ConciseDateFormatter(locator)
            ax_corr.xaxis.set_major_locator(locator)
            ax_corr.xaxis.set_major_formatter(formatter)

            plt.draw()

        def set_fit_limits(event):
            if len(selected_limits) < 2:
                print('Not enough limits selected')
                return
            # Clear the selected points list and update the plot
            limits_fit.clear()
            for limit in selected_limits[-2:]:
                limits_fit.append(limit)
            plt.draw()

        correction_done = False
        corrected_temperature = None
        def on_select_fit(label):
            nonlocal line_fit, line_fit_m, line_uncorr, line_corr, data_m, correction_done, corrected_temperature
            # create column with seconds since fit start
            correction_done = True  # initialize as True
            if label == 'none':
                correction_done = False
            if label == 'linear':
                fit_func = self.fit_func_linear
                p0 = [data_non_m['temperature'].iloc[0], 1E-5]
            elif label == 'polynomial':
                fit_func = self.fit_func_poly_5
                p0 = [data_b['temperature'].iloc[-1], 1, 1, 1, 1, 1]
            elif label == 'newton':
                fit_func = self.fit_func_newton
                p0 = [data_non_m['temperature'].iloc[0], data_non_m['temperature'].iloc[-1], 1E-4]
            try:
                for line in [line_fit, line_fit_m, line_uncorr, line_corr]:
                    if line is not None:
                        if line != []:
                            line = line.pop(0)
                            line.remove()
                if not correction_done:
                    plt.draw()
                    return
            except ValueError as error:
                print(error)
                pass
            # choose data and calculate fit
            data_to_fit = data_non_m[(data_non_m['time'] > limits_fit[0]) & (data_non_m['time'] < limits_fit[1]) &
                                     ((data_non_m['time'] > data_m['time'].iloc[-1] + 3 * heating_time_interval) |
                                      (data_non_m['time'] < data_m['time'].iloc[0]))]
            fit_params, fit_pcov = sc.optimize.curve_fit(fit_func, data_to_fit['seconds_combined'], data_to_fit['temperature'], p0=p0)
            fit_params_err = np.sqrt(np.diag(fit_pcov)) if fit_pcov is not None else None

            fit_m = fit_func(data_m['seconds_combined'], *fit_params)
            data_to_fit = data_to_fit.assign(fit_ydata=fit_func(data_to_fit['seconds_combined'], *fit_params))
            # check error of fit, if fit is good enough, add temp uncertainty from correction to data
            fit_error = self.calculate_fit_error(data_to_fit['temperature'], data_to_fit['fit_ydata'])
            fit_err_lim = 0.2
            if fit_error < fit_err_lim:
                if fit_func == self.fit_func_linear:
                    fit_label = 'Linear'
                    data_m = data_m.assign(
                        temperature_corr_err=np.sqrt(np.sum([(data_m['seconds_combined'] ** ii * p_err) ** 2
                                                             for ii, p_err in enumerate(fit_params_err)])))
                elif fit_func == self.fit_func_poly_5:
                    fit_label = 'Polynomial (5th)'
                    data_m = data_m.assign(
                        temperature_corr_err=np.sqrt(np.sum([(data_m['seconds_combined'] ** ii * p_err) ** 2
                                                             for ii, p_err in enumerate(fit_params_err)])))
                elif fit_func == self.fit_func_newton:
                    fit_label = 'Newton'
                    data_m = data_m.assign(
                        temperature_corr_err=self.fit_func_newton_err(data_m['seconds_combined'], fit_params,
                                                                      fit_params_err))


                corrected_temperature = data_m['temperature'] - fit_m + start_temp
                data_m_and_block = data_combined[(data_combined['time'] < data_m['time'].iloc[-1] +
                                                  3 * heating_time_interval) &
                                                 (data_combined['time'] > data_m['time'].iloc[0])]
                data_m_and_block = data_m_and_block.assign(fit_ydata=fit_func(data_m_and_block['seconds_combined'],
                                                                              *fit_params))
                # plot lines
                data_to_fit_with_gap = data_to_fit.set_index('seconds_combined'
                                                             ).reindex(data_combined['seconds_combined']).reset_index()
                line_fit = ax_corr.plot(data_to_fit_with_gap['time'], data_to_fit_with_gap['fit_ydata'], linestyle='dashed', color='red',
                             label=f'{fit_label} Fit')
                line_fit_m = ax_corr.plot(data_m_and_block['time'], data_m_and_block['fit_ydata'], linestyle='dashed',
                                          color='red', alpha=0.25)
                #line_uncorr = ax_corr.plot(data_m['time'], data_m['temperature_uncorr'], color='blue',
                #                           label='THS Temperature')
                line_corr = ax_corr.plot(data_m['time'], corrected_temperature, color='green', linestyle='dotted',
                                              label='Corrected Temperature')
                ylims = (min(data_to_fit['fit_ydata'].min(), data_m['temperature'].min(),
                             corrected_temperature.min(), data_m_and_block['fit_ydata'].min()) - 1,
                         max(data_to_fit['fit_ydata'].max(), data_m['temperature'].max(),
                             corrected_temperature.max(), data_m_and_block['fit_ydata'].max()) + 1)

            else:
                #line_uncorr = ax_corr.plot(data_m['time'], data_m['temperature'], color='blue', label='THS Temperature')
                ylims = ax_corr.get_ylim()
                correction_done = False
                print('Fit Failed')

            ax_corr.set_ylim(ylims)

            ax_corr.legend(loc='best')
            plt.draw()

            # plot figure with deviation from fit
            fig_corr_dev, ax_corr_dev = plt.subplots()
            ax_corr_dev.set_xlabel('Time')
            ax_corr_dev.set_ylabel('Temperature Difference from Fit (K)')
            ax_corr_dev.set_ylim(-0.5, 0.5)
            ax_corr_dev.set_xlim(ax_corr.get_xlim())
            locator = mdates.AutoDateLocator(minticks=3, maxticks=9)
            formatter = mdates.ConciseDateFormatter(locator)
            ax_corr_dev.xaxis.set_major_locator(locator)
            ax_corr_dev.xaxis.set_major_formatter(formatter)
            ax_corr_dev.xaxis.set_major_locator(locator)
            ax_corr_dev.xaxis.set_major_formatter(formatter)

            ax_corr_dev.plot(data_to_fit['time'], data_to_fit['fit_ydata'] - data_to_fit['temperature'], color='black')
            ax_corr_dev.grid(axis='both', linestyle='dashed', linewidth=0.5)

            path_fig_corr_dev = path_file_m_corr.replace('.txt', '_fit_dev.png')
            fig_corr_dev.canvas.mpl_connect('close_event',
                                            lambda event: save_figure(event, fig_corr_dev, path_fig_corr_dev))
            plt.show()

        def set_heating_time(text):
            nonlocal heating_time_interval
            try:
                heating_time_interval = pd.Timedelta(float(text), 'min')
            except ValueError:
                print('TextBox set_heating_time invalid input')

        def on_reset(event):
            selected_limits.clear()
            x_lims = get_xlims(data_b, data_m, data_a)
            ax_corr.set_ylim(get_ylims(data_b, data_m, data_a))
            ax_corr.set_xlim(x_lims)

            locator = mdates.AutoDateLocator(minticks=3, maxticks=9)
            formatter = mdates.ConciseDateFormatter(locator)
            ax_corr.xaxis.set_major_locator(locator)
            ax_corr.xaxis.set_major_formatter(formatter)
            plt.draw()

        reset_data = False

        def on_reset_data(event):
            nonlocal reset_data
            reset_data = True
            plt.close()

        fig_corr, ax_corr = plt.subplots()
        ax_corr.plot(data_b['time'], data_b['temperature'], color='blue', picker=5)
        ax_corr.plot(data_m['time'], data_m['temperature'], color='blue', picker=5, label='THS Temperature')
        ax_corr.plot(data_a['time'], data_a['temperature'], color='blue', picker=5)
        ax_corr.set_xlim(get_xlims(data_b, data_m, data_a))
        ax_corr.set_xlabel('Time')
        ax_corr.set_ylabel('Temperature (K)')
        ax_corr.legend(loc="best")
        ax_corr.grid(axis='both', linestyle='dashed', linewidth=0.5)


        on_reset(None)  # scale axis

        button_reset_data_ax = plt.axes([0.901, 0.90, 0.1, 0.05])
        button_reset_data = Button(button_reset_data_ax, 'Reset Data')
        button_reset_data.on_clicked(on_reset_data)

        button_reset_ax = plt.axes([0.901, 0.8, 0.1, 0.05])
        button_reset = Button(button_reset_ax, 'Reset Lims')
        button_reset.on_clicked(on_reset)

        button_set_limits_ax = plt.axes([0.901, 0.75, 0.1, 0.05])
        button_set_limits = Button(button_set_limits_ax, 'Set limits')
        button_set_limits.on_clicked(set_limits)

        button_set_fit_limits_ax = plt.axes([0.901, 0.7, 0.1, 0.05])
        button_set_fit_limits = Button(button_set_fit_limits_ax, 'Set fit limits')
        button_set_fit_limits.on_clicked(set_fit_limits)

        button_fits_ax = plt.axes([0.901, 0.45, 0.1, 0.20])
        button_fits = RadioButtons(button_fits_ax, ['none', 'linear', 'polynomial', 'newton'])
        button_fits.on_clicked(on_select_fit)

        textbox_heatingtime_ax = plt.axes([0.901, 0.4, 0.1, 0.05])
        textbox_heatingtime = TextBox(textbox_heatingtime_ax, label='',
                                      initial=heating_time_interval.total_seconds() / 60)
        textbox_heatingtime.on_submit(set_heating_time)


        fig_corr.canvas.mpl_connect('pick_event', on_pick)
        path_fig_corr = path_file_m_corr.replace('.txt', '_fit.png')
        fig_corr.canvas.mpl_connect('close_event', lambda event: save_figure(event, fig_corr, path_fig_corr,[textbox_heatingtime_ax, button_set_limits_ax, button_reset_data_ax, button_set_fit_limits_ax, button_fits_ax,button_reset_ax]))
        plt.show()
        if reset_data:
            return 'reset'
        else:
            if correction_done:
                data_m = data_m.assign(temperature_uncorr=data_m['temperature'],
                                       temperature=corrected_temperature)
                data_m.to_csv(path_file_m_corr, index=False)
                return data_m
            else:
                return None

    def find_linear_parts(self, data, min_linear_time):
        '''
        Finds the longest linear part of a temperature_diff vs log10(seconds) curve.
        data : pd.DataFrame, including seconds and temperature_diff columns
        min_linear_time : float, minimal duration of linear interval (seconds)

        returns:
        '''
        seconds_log = data['seconds_log'].values
        temp_diff = data['temperature_diff'].values
        # interpolate data into equal log-spaced points
        point_num = seconds_log.size // int(seconds_log.size*0.008)  # arbitrary so curve is nice and smooth
        interp_func = sc.interpolate.interp1d(seconds_log, temp_diff)
        seconds_log_spaced = np.linspace(seconds_log.min(), seconds_log.max(), point_num)
        temp_diff_log_spaced = interp_func(seconds_log_spaced)
        # smooth data with savgol filter
        win_size = point_num // int(point_num*0.15)  # arbitrary so curve is nice and smooth
        temp_diff_log_spaced_smoothed = sc.signal.savgol_filter(temp_diff_log_spaced, win_size, 3)

        win_size = point_num // int(point_num*0.0625)  # arbitrary so curve is nice and smooth
        der1 = np.gradient(temp_diff_log_spaced_smoothed, seconds_log_spaced)
        der1_smoothed = sc.signal.savgol_filter(der1, win_size, 3)

        ### find stationary states in the first derivative which correspond to linear parts in the data
        intvl = point_num // 20  # interval of values to check for linearity (left and right)
        intvl_size = np.mean(np.diff(seconds_log_spaced)) * intvl  # interval size in log10 space
        stationary_x_values = np.empty((0, 1))  # init
        stationary_y_values = np.empty((0, 1))  # init
        # initializations for finding the longest interval
        currently_in_stationary_interval = False
        largest_interval_size = 0
        interval_sizes = []
        interval_starts = []
        interval_start = None
        last_x_value = None
        # iterate over intervals in first derivative, check for stationary and save to arrays
        for ii in range(intvl, der1.size - intvl):
            temp_diff_values = temp_diff_log_spaced[ii - intvl:ii + intvl]
            der1_values = der1_smoothed[ii - intvl:ii + intvl]
            secs_log = seconds_log_spaced[ii - intvl:ii + intvl]
            is_stat, mean = self.is_stationary(secs_log, der1_values, intvl_size, max_deviation=0.1)
            x = np.mean(secs_log)
            y = np.mean(temp_diff_values) if is_stat else np.nan
            stationary_x_values = np.append(stationary_x_values, x)
            stationary_y_values = np.append(stationary_y_values, y)

            # find the longest interval (seconds) with continuous stationary values
            if not np.isnan(y):
                if not currently_in_stationary_interval:
                    currently_in_stationary_interval = True
                    interval_start = x
                last_x_value = x
            else:
                if currently_in_stationary_interval:
                    currently_in_stationary_interval = False
                    interval_size = np.exp(last_x_value) - np.exp(interval_start)
                    interval_sizes.append(interval_size)
                    interval_starts.append(np.exp(interval_start))
        # append very last interval if data ends with stationary state
        if currently_in_stationary_interval:
            interval_size = np.exp(last_x_value) - np.exp(interval_start)
            interval_sizes.append(interval_size)
            interval_starts.append(np.exp(interval_start))
        sorted_lists = sorted(zip(interval_sizes, interval_starts))
        sorted_lists = [(size, start) for size, start in sorted_lists if size >= min_linear_time]
        try:
            interval_sizes, interval_starts = zip(*sorted_lists)
            return interval_starts, interval_sizes
        except ValueError as error:
            #print(error) # not enough values to unpack (expected 2, got 0) --> no linear parts found
            return None, None

    def get_best_fits(self, data, min_linear_time, filepath):
        fit_data_list = []
        interval_starts, interval_sizes = self.find_linear_parts(data, min_linear_time)
        if interval_starts is None:
            return None, None, None

        ii = -1
        iterations_counter = 0
        df_results = pd.DataFrame()
        new_start, new_size = None, None
        extending_fit = False
        while True:
            ii += 1
            iterations_counter += 1
            # stop condition (also considering infinite loop due too abs.max() and tau_min corrections
            if ii >= len(interval_starts) or iterations_counter > 6 * len(interval_starts):
                #print('break due to end of list', ii >= len(interval_starts), 'or iteration counter', iterations_counter > 6 * len(interval_starts))
                break
            if new_start:
                interval_start = new_start
            else:
                interval_start = interval_starts[ii]
            if new_size:
                interval_size = new_size
            else:
                interval_size = interval_sizes[ii]
            # indicator column where fit is placed
            data['fit'] = (data['seconds'] >= interval_start) & (data['seconds'] <= interval_start + interval_size)
            fit_popt, fit_pcov = sc.optimize.curve_fit(f=self.fit_func_linear, xdata=data[data['fit']]['seconds_log'],
                                           ydata=data[data['fit']]['temperature_diff'],
                                           sigma=data[data['fit']]['temperature_diff_error'], absolute_sigma=True,
                                           p0=[0, 1], bounds=([-np.inf, 0], [np.inf, np.inf]))
            fit_popt_err = np.sqrt(np.diag(fit_pcov))

            data = data.assign(fit_ydata=self.fit_func_linear(data['seconds_log'], *fit_popt))
            data = data.assign(fit_dev=data['temperature_diff'] - data['fit_ydata'])

            result_dict = self.calculate_thermal_conductivity_from_fit(data, fit_popt, fit_popt_err, filepath)

            result_dict['idx'] = ii
            fit_data_list.append(data)

            '''
            plt.close('all')
            fig, ax = plt.subplots()
            ax.plot(data['seconds'], data['temperature_diff'])
            ax.plot(data[data['fit']]['seconds'], data[data['fit']]['fit_ydata'], color='red')
            ax.set_xscale('log', base=np.e)
            ax2 = ax.twinx()
            ax2.plot(data[data['fit']]['seconds'], data[data['fit']]['fit_dev'], color='green')
            plt.show()
            '''

            # sort out fits that start too early or end too late
            if result_dict['tau_min'] < 1.95:
                extending_fit = False
                #print('tau_min too small', result_dict['tau_min'])
                ii -= 1
                new_start = (2.0 * self.ths_width)**2 / (4 * result_dict['thermal_diff'])
                new_size = interval_size - (new_start - interval_start)
                if new_size <= 0:  # do not alter limits if size would vanish
                    #print('vanishes')
                    ii += 1
                    new_start, new_size = None, None
                continue
            elif result_dict['tau_max'] > result_dict['tau_max_limit']:
                extending_fit = False
                #print('tau_max too large', result_dict['tau_max'], 'limit:', result_dict['tau_max_limit'])
                ii -= 1
                new_end = (result_dict['tau_max_limit'] * self.ths_width)**2 / (4 * result_dict['thermal_diff'])
                new_size = new_end - interval_start
                if new_size <= 0:  # do not alter limits if size would vanish
                    ii += 1
                    new_size = None
                continue
            elif result_dict['tau_max'] < result_dict['tau_max_limit'] and not extending_fit:
                extending_fit = True
                ii -= 1
                new_end = (result_dict['tau_max_limit'] * self.ths_width) ** 2 / (4 * result_dict['thermal_diff'])
                new_size = new_end - interval_start
                # save latest fit if currently in last interation
                if ii+1 >= len(interval_starts) or iterations_counter+1 > 6 * len(interval_starts):
                    df_results = pd.concat([df_results, pd.DataFrame(result_dict, index=[0])], ignore_index=True)
                    new_start = None
                    new_size = None
                continue
            elif data[data['fit']]['fit_dev'].abs().max() > 0.04:
                extending_fit = False
                #print('abs dev too large', data[data['fit']]['fit_dev'].abs().max())
                ii -= 1
                new_start = interval_start + interval_size/5
                new_size = interval_size - (new_start - interval_start)
                if new_size <= 0:  # do not alter limits if size would vanish
                    ii += 1
                    new_start, new_size = None, None
                continue
            else:
                #print('added fit with', fit_popt, fit_popt_err)
                df_results = pd.concat([df_results, pd.DataFrame(result_dict, index=[0])], ignore_index=True)
                new_start = None
                new_size = None
        return df_results, fit_data_list

    def get_fit_interactive(self, data, file_path_m):
        mpl.use('TkAgg')  # for interactive plots
        plt.close('all')
        data_orig = data.copy()
        selected_limits = []
        limits_fit = []
        df_result, line_fit, line_fit_extrapolated, text = None, None, None, None

        def on_reset(event):
            nonlocal data, df_result, selected_limits, limits_fit, line_fit, line_fit_extrapolated, text
            selected_limits.clear()
            limits_fit.clear()
            df_result = None
            data = data_orig.copy()
            try:
                for line in [line_fit, line_fit_extrapolated]:
                    if line is not None:
                        if line != []:
                            line = line.pop(0)
                            line.remove()
                if text is not None:
                    text.remove()
            except ValueError as error:
                print(error)
                pass
            plt.draw()

        def on_pick(event):
            nonlocal selected_limits
            x, y = event.artist.get_data()
            x_date = x[event.ind[0]]
            selected_limits.append(x_date)
            print('Slected:', x_date)

        def set_fit_limits(event):
            nonlocal selected_limits, limits_fit
            if len(selected_limits) < 2:
                print('Not enough limits selected')
                return
            # Clear the selected points list and update the plot
            limits_fit.clear()
            for limit in selected_limits[-2:]:
                limits_fit.append(limit)
            plt.draw()

        def on_fit_data(event):
            nonlocal data, df_result, line_fit, line_fit_extrapolated, text, limits_fit
            try:
                for line in [line_fit, line_fit_extrapolated]:
                    if line is not None:
                        if line != []:
                            line = line.pop(0)
                            line.remove()
                if text is not None:
                    text.remove()
            except ValueError as error:
                print(error)
                pass

            data['fit'] = (data['seconds'] >= limits_fit[0]) & (data['seconds'] <= limits_fit[1])
            fit_popt, fit_pcov = sc.optimize.curve_fit(f=self.fit_func_linear, xdata=data[data['fit']]['seconds_log'],
                                           ydata=data[data['fit']]['temperature_diff'],
                                           sigma=data[data['fit']]['temperature_diff_error'], absolute_sigma=True,
                                           p0=[0, 1], bounds=([-np.inf, 0], [np.inf, np.inf]))
            fit_popt_err = np.sqrt(np.diag(fit_pcov))

            data = data.assign(fit_ydata=self.fit_func_linear(data['seconds_log'], *fit_popt))
            data = data.assign(fit_dev=data['temperature_diff'] - data['fit_ydata'])

            result_dict = self.calculate_thermal_conductivity_from_fit(data, fit_popt, fit_popt_err, file_path_m)
            df_result = pd.DataFrame(result_dict, index=[0])

            if df_result is not None:
                (thermal_conductivity, thermal_conductivity_error, thermal_diffusivity, thermal_diffusivity_error,
                 tau_min, tau_max, tau_max_limit, mean_temp, mean_temp_err) = (
                    df_result['thermal_cond'].iloc[0], df_result['thermal_cond_err'].iloc[0],
                    df_result['thermal_diff'].iloc[0], df_result['thermal_diff_err'].iloc[0],
                    df_result['tau_min'].iloc[0], df_result['tau_max'].iloc[0], df_result['tau_max_limit'].iloc[0],
                    df_result['temp'].iloc[0], df_result['temp_err'].iloc[0])

                line_fit = ax_cond.plot(data[data['fit']]['seconds'], data[data['fit']]['fit_ydata'], color='blue',
                                        linestyle='dashed', linewidth=2)  # fit data in fit range
                data_non_fit = data.copy()
                data_non_fit.loc[
                    data['fit'], ['seconds', 'fit_ydata']] = np.nan  # set values of fit to nan to avoid overlap in plot
                line_fit_extrapolated = ax_cond.plot(data_non_fit['seconds'], data_non_fit['fit_ydata'], color='tab:red',
                                                     linestyle='dotted', linewidth=2)  # fit data outside fit range

                annotation = (f'T = ({mean_temp:.3f} \u00B1 {mean_temp_err:.3f}) K\n' +
                              f'k = ({thermal_conductivity:.7f} \u00B1 {thermal_conductivity_error:.7f})' + ' W m$^{-1}$ K$^{-1}$\n' +
                              f'a = ({thermal_diffusivity * 1E6:.7f} \u00B1 {thermal_diffusivity_error * 1E6:.7f})' + ' mm$^2$ s$^{-1}$\n' +
                              '$\\tau_\\mathrm{min} = $' + f'{tau_min:.1f}\n' +
                              '$\\tau_\\mathrm{max} = $' + f'{tau_max:.1f}\n' +
                              '$\\tau_\\mathrm{max lim} = $' + f'{tau_max_limit:.1f}')
                text = ax_cond.text(0.01, 0.99, annotation, transform=ax_cond.transAxes, ha='left', va='top',
                                    multialignment='left')


                # plot data deviation from fit
                fig_cond_dev = plt.figure()
                ax_cond_dev = fig_cond_dev.subplots()
                ax_cond_dev.set_xlabel('Time (s)')
                ax_cond_dev.set_ylabel('Temperature difference deviation from fit (K)')
                ax_cond_dev.set_ylim(-0.05, 0.05)

                ax_cond_dev.plot(data[data['fit']]['seconds'], data[data['fit']]['fit_dev'], color='black')
                ax_cond_dev.grid(axis='both', linestyle='dashed', linewidth=0.5, alpha=0.5)
            plt.show()
            return df_result, data

        fig_cond, ax_cond = plt.subplots()
        ax_cond.set_xlabel('Time (s)')
        ax_cond.set_ylabel('Temperature difference (K)')
        ax_cond.set_xscale('log', base=np.e)

        def log_tick_formatter(val, pos):
            return f'{val:.1f}'
        ax_cond.xaxis.set_major_formatter(mpl.ticker.FuncFormatter(log_tick_formatter))
        ax_cond.xaxis.set_minor_formatter(mpl.ticker.FuncFormatter(log_tick_formatter))

        ax_cond.set_ylim(0, data['temperature_diff'].max() + 0.1)
        ax_cond.set_xlim(1, data['seconds'].iloc[-1])
        ax_cond.plot(data['seconds'], data['temperature_diff'], color='black', label='Difference', picker=5)  # original data

        ax_cond.grid(axis='both', which='both', linestyle='dashed', linewidth=0.5, alpha=0.5)

        button_reset_ax = plt.axes([0.901, 0.90, 0.1, 0.05])
        button_reset = Button(button_reset_ax, 'Reset')
        button_reset.on_clicked(on_reset)

        button_set_fit_limits_ax = plt.axes([0.901, 0.80, 0.1, 0.05])
        button_set_fit_limits = Button(button_set_fit_limits_ax, 'Set limits')
        button_set_fit_limits.on_clicked(set_fit_limits)

        button_fit_data_ax = plt.axes([0.901, 0.75, 0.1, 0.05])
        button_fit_data = Button(button_fit_data_ax, 'Fit Data')
        button_fit_data.on_clicked(on_fit_data)
        fig_cond.canvas.mpl_connect('pick_event', on_pick)
        plt.show()

        return df_result, data

    def calculate_thermal_conductivity_from_fit(self, data, p_opt, p_err, filepath):
        '''
        data: data with additional columns 'fit' to indicate fitted interval with True and
                                           'fit_ydata' values of linear fit
        '''
        m = p_opt[1]  # slope
        m_err = p_err[1]  # slope err
        n = p_opt[0]  # intercept
        n_err = p_err[0]  # intercept err

        # calculate thermal conductivity from fit (see Hammerschmidt,Sabuga 1999)
        thermal_cond = (data['voltage'].mean() * data['current'].mean() / (4 * np.pi * self.ths_length * m))
        thermal_diff = (self.ths_width ** 2 / (4 * np.exp(3 - 0.5772)) * np.exp(n / m))  # with euler constant 0.5772 from Hammerschmidt,Sabuga 1999
        # initial values for fitted range
        fit_start = data[data['fit']]['seconds'].iloc[0]
        fit_end = data[data['fit']]['seconds'].iloc[-1]
        tau_min = np.sqrt(4 * thermal_diff * fit_start) / self.ths_width
        tau_max = np.sqrt(4 * thermal_diff * fit_end) / self.ths_width

        t_max = self.probing_depth ** 2 / (2 * thermal_diff)
        tau_max_limit = np.sqrt(4 * thermal_diff * t_max) / self.ths_width

        # uncertainty assessment
        current_err = data['current'].std() + np.sqrt((self.shunt_volt_error / self.shunt_resistance) ** 2 + (
                    data['shunt_voltage'].mean() * self.shunt_resistance_err / self.shunt_resistance ** 2) ** 2)
        thermal_conductivity_fit_error = np.sqrt((1 / (4 * np.pi * self.ths_length * m)) ** 2 * (
                (self.voltage_error * data['current'].mean()) ** 2 + (
                 current_err * data['voltage'].mean()) ** 2 + (
                 m_err * data['voltage'].mean() * data['current'].mean() / m) ** 2))
        thermal_conductivity_linearmodel_error = thermal_cond * 12.7 * (tau_min * tau_max ** 0.85) ** (
            -1) / 100  # with empirical parameters L1=12.7 and L2=0.85
        thermal_cond_err = thermal_conductivity_fit_error + thermal_conductivity_linearmodel_error

        thermal_diffusivity_fit_error = self.ths_width ** 2 / (4 * np.exp(3 - 0.5772)) * np.sqrt(
            (n_err / m * np.exp(n / m)) ** 2 + (m_err * n / m ** 2 * np.exp(n / m)) ** 2)
        thermal_diffusivity_linearmodel_error = thermal_diff * 28.5 * (tau_min * tau_max ** 0.67) ** (
            -1) / 100  # with empirical parameters A1=28.5 and A2=0.67
        thermal_diff_err = thermal_diffusivity_fit_error + thermal_diffusivity_linearmodel_error

        # use real temperature is values were corrected previously
        if filepath.endswith('_corrected_THS.txt'):
            mean_temp = ((data[data['fit']]['temperature_uncorr'].max() - data[data['fit']]['temperature_uncorr'].min()) / 2 +
                         data[data['fit']]['temperature_uncorr'].min())
            mean_temp_err = (
                    (data[data['fit']]['temperature_uncorr'].max() - data[data['fit']]['temperature_uncorr'].min()) / 2 +
                    data[data['fit']]['temperature_diff_error'].max())
        else:
            mean_temp = ((data[data['fit']]['temperature'].max() - data[data['fit']]['temperature'].min()) / 2 +
                         data[data['fit']]['temperature'].min())
            mean_temp_err = ((data[data['fit']]['temperature'].max() - data[data['fit']]['temperature'].min()) / 2 +
                             data[data['fit']]['temperature_diff_error'].max())

        result_dict = {'thermal_cond': thermal_cond, 'thermal_cond_err': thermal_cond_err,
                       'thermal_cond_fit_err':thermal_conductivity_fit_error,
                       'thermal_cond_linearmodel_err': thermal_conductivity_linearmodel_error,
                       'thermal_diff': thermal_diff, 'thermal_diff_err': thermal_diff_err,
                       'thermal_diff_fit_err': thermal_diffusivity_fit_error,
                       'thermal_diff_linearmodel_err': thermal_diffusivity_linearmodel_error,
                       'temp': mean_temp, 'temp_err': mean_temp_err,
                       'tau_min': tau_min, 'tau_max': tau_max, 'tau_max_limit': tau_max_limit,
                       'fit_start': fit_start, 'fit_end': fit_end,
                       'm': m, 'm_err': m_err, 'n': n, 'n_err': n_err
                       }
        return result_dict

    def plot_fit_and_deviation(self, data, df_result, filepath):
        if df_result is not None:  # None in case no fit was found --> plot original data without fit then
            (thermal_conductivity, thermal_conductivity_error, thermal_diffusivity, thermal_diffusivity_error,
             tau_min, tau_max, tau_max_limit, mean_temp, mean_temp_err) = (
                df_result['thermal_cond'].iloc[0], df_result['thermal_cond_err'].iloc[0],
                df_result['thermal_diff'].iloc[0], df_result['thermal_diff_err'].iloc[0],
                df_result['tau_min'].iloc[0], df_result['tau_max'].iloc[0], df_result['tau_max_limit'].iloc[0],
                df_result['temp'].iloc[0], df_result['temp_err'].iloc[0])
        else:
            (thermal_conductivity, thermal_conductivity_error, thermal_diffusivity, thermal_diffusivity_error,
             tau_min, tau_max, tau_max_limit, mean_temp, mean_temp_err) = 9*[np.nan]

        # plot data with fit
        fig_cond = plt.figure()
        ax_cond = fig_cond.subplots()
        ax_cond.set_xlabel('Time (s)')
        ax_cond.set_ylabel('Temperature difference (K)')
        ax_cond.set_xscale('log', base=np.e)
        def log_tick_formatter(val, pos):
            return f'{val:.1f}'
        # Apply the custom formatter to the x-axis
        ax_cond.xaxis.set_major_formatter(mpl.ticker.FuncFormatter(log_tick_formatter))
        ax_cond.xaxis.set_minor_formatter(mpl.ticker.FuncFormatter(log_tick_formatter))

        ax_cond.set_ylim(0, data['temperature_diff'].max() + 0.1)
        ax_cond.set_xlim(1, data['seconds'].iloc[-1])
        ax_cond.plot(data['seconds'], data['temperature_diff'], color='black', label='Difference')  # original data

        if df_result is not None:
            ax_cond.plot(data[data['fit']]['seconds'], data[data['fit']]['fit_ydata'], color='blue',
                         linestyle='dashed', linewidth=2)  # fit data in fit range
            data_non_fit = data.copy()
            data_non_fit.loc[data['fit'], ['seconds', 'fit_ydata']] = np.nan  # set values of fit to nan to avoid overlap in plot
            ax_cond.plot(data_non_fit['seconds'], data_non_fit['fit_ydata'], color='tab:red',
                         linestyle='dotted', linewidth=2)  # fit data outside fit range

            annotation = (f'T = ({mean_temp:.3f} \u00B1 {mean_temp_err:.3f}) K\n' +
                          f'k = ({thermal_conductivity:.7f} \u00B1 {thermal_conductivity_error:.7f})' + ' W m$^{-1}$ K$^{-1}$\n' +
                          f'a = ({thermal_diffusivity * 1E6:.7f} \u00B1 {thermal_diffusivity_error * 1E6:.7f})' + ' mm$^2$ s$^{-1}$\n' +
                          '$\\tau_\\mathrm{min} = $' + f'{tau_min:.1f}\n' +
                          '$\\tau_\\mathrm{max} = $' + f'{tau_max:.1f}\n' +
                          '$\\tau_\\mathrm{max lim} = $' + f'{tau_max_limit:.1f}')
            ax_cond.text(0.01, 0.99, annotation, transform=ax_cond.transAxes, ha='left', va='top',
                         multialignment='left')
        ax_cond.grid(axis='both', which='both', linestyle='dashed', linewidth=0.5, alpha=0.5)
        path_fig_cond = filepath.replace('.txt', '_thermal_cond.png')
        fig_cond.savefig(path_fig_cond, dpi=300, bbox_inches='tight')

        if df_result is not None:
            # plot data deviation from fit
            fig_cond_dev = plt.figure()
            ax_cond_dev = fig_cond_dev.subplots()
            ax_cond_dev.set_xlabel('Time (s)')
            ax_cond_dev.set_ylabel('Temperature difference deviation from fit (K)')
            ax_cond_dev.set_ylim(-0.05, 0.05)

            ax_cond_dev.plot(data[data['fit']]['seconds'], data[data['fit']]['fit_dev'], color='black')
            ax_cond_dev.grid(axis='both', linestyle='dashed', linewidth=0.5, alpha=0.5)

            path_fig_cond_dev = filepath.replace('.txt', '_thermal_cond_deviation.png')
            fig_cond_dev.savefig(path_fig_cond_dev, dpi=300, bbox_inches='tight')

    def prepare_data_for_calculations(self, data, start_temp, file_path_m):
        # prepare data for calculations
        data = data.assign(seconds=(data['time'] - data['time'].iloc[0]).dt.total_seconds())
        data = data[data['seconds'] > 0]
        data = data.assign(seconds_log=np.log(data['seconds']))
        if data['temperature'].isna().all():  # in the case correction didn't work properly
            data = data.assign(temperature=data['temperature_uncorr'])
        data = data.assign(temperature_diff=data['temperature'] - start_temp)

        data = data.assign(current=data['shunt_voltage'] / self.shunt_resistance)
        data = data.assign(current_error=np.sqrt((self.shunt_volt_error / self.shunt_resistance) ** 2 + (
                data['shunt_voltage'] * self.shunt_resistance_err / self.shunt_resistance ** 2) ** 2))

        data = data.assign(resistance=data['voltage'] / data['current'])
        data = data.assign(resistance_error=np.sqrt((self.voltage_error / data['current']) ** 2 +
                                                    (data['voltage'] * data['current_error'] / data[
                                                        'current'] ** 2) ** 2))
        if 'temperature_corr_err' not in data.columns:  # in case no correction was done
            data['temperature_corr_err'] = 0
        else:
            data['temperature_corr_err'] = 0  # set to zero for now, since error is wierdly large
        data = data.assign(temperature_error=(1 / 2 * (self.temperature_fit_func(data['resistance'].values +
                                                                                 data['resistance_error'].values)
                                                       - self.temperature_fit_func(data['resistance'].values -
                                                                                   data['resistance_error'].values))
                                              + data['temperature_corr_err']))
        data = data.assign(temperature_diff_error=np.sqrt(data['temperature_error'].values ** 2 +
                                                          data['temperature_error'].iloc[0] ** 2))
        return data

    def calculate_thermal_cond_automatically(self, data, file_path_m, start_temp, min_linear_time):
        if 'temperature_uncorr' in data.columns:  # check if data was corrected
            file_path_m = file_path_m.replace('_THS.txt', '_corrected_THS.txt')

        data = self.prepare_data_for_calculations(data, start_temp, file_path_m)

        # get linear fit from stationary states in first derivative, best fit is formatted into dataframe
        try:
            df_results, fit_data_list = self.get_best_fits(data, min_linear_time, file_path_m)
        except Exception as error:
            print(error)
            df_results = pd.DataFrame()
        if df_results.shape[0] == 0:  # return None if no result found
            self.plot_fit_and_deviation(data, None, file_path_m)
            return None
        # get git with the smallest tau_min
        df_results = df_results.sort_values(by='tau_min')
        df_result = df_results.iloc[:1]
        idx = df_result['idx'].iloc[0]
        data = fit_data_list[idx]


        filename = os.path.basename(file_path_m)
        datetime = pd.to_datetime(filename[:19], format='%Y-%m-%d-%H-%M-%S')
        is_corr = filename.endswith('_corrected_THS.txt')
        df_result = df_result.assign(datetime=datetime, is_corrected=is_corr)
        # save fit data as csv
        df_result.to_csv(file_path_m.replace(filename, 'ResultData.txt'), index=False)

        self.plot_fit_and_deviation(data, df_result, file_path_m)
        return df_result[['datetime', 'is_corrected', 'temp', 'temp_err', 'thermal_cond', 'thermal_cond_err',
                          'thermal_diff', 'thermal_diff_err', 'tau_min', 'tau_max', 'tau_max_limit']]


    def calculate_thermal_cond_manually(self, data, file_path_m, start_temp):
        if 'temperature_uncorr' in data.columns:  # check if data was corrected
            file_path_m = file_path_m.replace('_THS.txt', '_corrected_THS.txt')
        filename = os.path.basename(file_path_m)

        data = self.prepare_data_for_calculations(data, start_temp, file_path_m)
        df_result = None
        if True:#try:
            df_result, data = self.get_fit_interactive(data, file_path_m)
        #except Exception as error:
        #    print(error)
        #    df_result = pd.DataFrame()
        if df_result is None:  # return None if no result found but plot data without fit
            self.plot_fit_and_deviation(data, None, file_path_m)
            file_path_r = file_path_m.replace(filename, 'ResultData.txt')
            if os.path.exists(file_path_r):
                os.remove(file_path_r)
            return None

        datetime = pd.to_datetime(filename[:19], format='%Y-%m-%d-%H-%M-%S')
        is_corr = filename.endswith('_corrected_THS.txt')
        df_result = df_result.assign(datetime=datetime, is_corrected=is_corr)
        # save fit data as csv
        df_result.to_csv(file_path_m.replace(filename, 'ResultData.txt'), index=False)

        self.plot_fit_and_deviation(data, df_result, file_path_m)
        return df_result[['datetime', 'is_corrected', 'temp', 'temp_err', 'thermal_cond', 'thermal_cond_err',
                          'thermal_diff', 'thermal_diff_err', 'tau_min', 'tau_max', 'tau_max_limit']]


    def correct_and_evaluate_measurement(self, directory_path, re_evaluate_data=False, re_correct_data=False,
                                         do_correction_manually=False, do_evaluation_manually=False,
                                         min_time_lin_fit=50):

        columns = ['num', 'datetime', 'is_corrected', 'temp', 'temp_err', 'thermal_cond', 'thermal_cond_err',
                   'thermal_diff', 'thermal_diff_err', 'tau_min', 'tau_max', 'tau_max_limit', 'mean_power']
        dtypes = {'num': int, 'is_corrected': bool, 'temp': 'float64', 'temp_err': 'float64',
                  'thermal_cond': 'float64', 'thermal_cond_err': 'float64',
                  'thermal_diff': 'float64', 'thermal_diff_err': 'float64',
                  'tau_min': 'float64', 'tau_max': 'float64', 'tau_max_limit': 'float64',
                  'mean_power': 'float64'}
        # create dataframe for new evaluations
        data_evaluated_new = pd.DataFrame(columns=columns)
        # find preexistent evaluation data, which will be skipped during further processing
        try:
            data_evaluated = pd.read_csv(os.path.join(directory_path, 'Data.txt'), header=0, dtype=dtypes)
            data_evaluated['datetime'] = pd.to_datetime(data_evaluated['datetime'])
        except Exception as error:
            print(error)
            data_evaluated = pd.DataFrame(
                columns=['num', 'datetime', 'is_corrected', 'temp', 'temp_err', 'thermal_cond',
                         'thermal_cond_err', 'thermal_diff', 'thermal_diff_err', 'tau_min',
                         'tau_max', 'tau_max_limit', 'mean_power'])
            data_evaluated['num'].astype('int')
        # get all measurement folders based on naming
        measurement_folders = [element for element in os.listdir(directory_path)
                               if element.startswith(directory_path.split('/')[-1])]
        measurement_folders = sorted(measurement_folders, key=lambda x: os.path.basename(x))
        measurements_to_correct_manually = []
        measurements_to_fit_manually = []
        ii = -1
        while True:
            ii += 1
            if ii >= len(measurement_folders):
                break

            measurement_folder = measurement_folders[ii]
            try:
                measurement_folder_path = os.path.join(directory_path, measurement_folder)
                # check if number of measurement already exists in evaluation data file, skip if true
                num = int(measurement_folder_path.split(' - ')[0][-3:])
                print(f'{num}/{len(measurement_folders)}')
                if not re_evaluate_data:
                    if num in data_evaluated['num'].values:
                        continue

                # read all THS files into dataframe
                files = [file for file in os.listdir(measurement_folder_path) if (file.endswith('_THS.txt') and
                                                                                  not file.endswith(
                                                                                      'corrected_THS.txt'))]
                data_combined = []
                measurement_file_path = None
                for file in files:
                    file_path = os.path.join(measurement_folder_path, file)
                    df = pd.read_csv(file_path, header=0)
                    df = df.dropna()
                    if df['current'].mean() > 0.005:
                        measurement_file_path = file_path
                    if not df.empty:
                        data_combined.append(df)
                    if len(files) == 1:
                        measurement_file_path = file_path
                if data_combined:
                    data_combined = pd.concat(data_combined)
                    data_combined['time'] = pd.to_datetime(data_combined['time'])
                    data_combined = data_combined.sort_values(by='time')
                else:
                    print('No data available in folder:', measurement_folder_path)
                    continue
                if data_combined['current'].iloc[-1] > 0.005:
                    data_combined = data_combined.drop(data_combined.index[-1])
                # create seconds column
                data_combined['seconds_combined'] = (
                            data_combined['time'] - data_combined['time'].iloc[0]).dt.total_seconds()
                # get measurement data
                data_measurement = data_combined[data_combined['current'] > 0.005]
                # get data before and after (within limit of multiple heating time intervals)
                heating_time_interval = data_measurement['time'].iloc[-1] - data_measurement['time'].iloc[0]
                data_before = data_combined[(data_combined['time'] < data_measurement['time'].iloc[0]) &
                                            (data_combined['time'] > data_measurement['time'].iloc[0] -
                                             6 * heating_time_interval)]
                data_after = data_combined[(data_combined['time'] > data_measurement['time'].iloc[-1]) &
                                           (data_combined['time'] < data_measurement['time'].iloc[-1] +
                                            9 * heating_time_interval)]
                start_temperature = data_before['temperature'].iloc[-5:].mean()

                if not do_correction_manually:
                    data_measurement_corrected = self.correct_temp_gradient_automatically(data_measurement, data_before,
                                                                                     data_after, measurement_file_path,
                                                                                     start_temperature,
                                                                                     re_correct_data)
                    if data_measurement_corrected is None:
                        measurements_to_correct_manually.append(num)
                        print(num, 'could not be corrected automatically')
                        continue
                else:
                    data_measurement_corrected = self.correct_temp_gradient_manually(data_measurement, data_before,
                                                                                     data_after,measurement_file_path,
                                                                                     start_temperature,re_correct_data)
                    if isinstance(data_measurement_corrected, str):
                        if data_measurement_corrected == 'reset':
                            ii -= 1
                            continue
                    if data_measurement_corrected is None:
                        print(num, 'could not be corrected manually')
                        continue

                if not do_evaluation_manually:
                    result_data = self.calculate_thermal_cond_automatically(data_measurement_corrected,
                                                                            measurement_file_path,
                                                                            start_temperature, min_time_lin_fit)
                    if result_data is None:
                        measurements_to_fit_manually.append(num)
                        print(num, 'could not be evaluated automatically')
                        data_evaluated = data_evaluated[data_evaluated['num'] != num]  # remove old data
                        continue
                else:
                    result_data = self.calculate_thermal_cond_manually(data_measurement_corrected,
                                                                       measurement_file_path,
                                                                       start_temperature)
                    if result_data is None:
                        print(num, 'could not be evaluated manually')
                        data_evaluated = data_evaluated[data_evaluated['num'] != num]  # remove old data
                        continue


                # calculate power input into sample
                power_mean = data_measurement['current'].mean() * data_measurement['voltage'].mean()

                # reformat results and append to list
                result_data = result_data.assign(num=num)
                result_data = result_data.assign(mean_power=power_mean)
                data_evaluated_new = pd.concat([data_evaluated_new, result_data], ignore_index=True)
            except KeyboardInterrupt:
                break
        print('Measurements that have to be corrected manually:', measurements_to_correct_manually)
        print('Measurements that have to be evaluated manually:', measurements_to_fit_manually)
        print('creating data file')
        data_evaluated_new = data_evaluated_new.astype(data_evaluated.dtypes)
        data_evaluated_new = data_evaluated_new.drop_duplicates(subset=['num'], keep='last')
        if data_evaluated_new.empty:
            pass
        elif data_evaluated.empty:
            data_evaluated = data_evaluated_new
        else:
            # drop old evaluations that have been done again
            data_evaluated = data_evaluated[~data_evaluated['num'].isin(data_evaluated_new['num'])]
            data_evaluated = pd.concat([data_evaluated, data_evaluated_new], ignore_index=True)

        data_evaluated.sort_values(by='num', inplace=True)
        data_evaluated['num'] = data_evaluated['num'].apply(lambda x: f'{x:03d}')
        data_evaluated.to_csv(os.path.join(directory_path, 'Data.txt'), sep=',', index=False)
        return measurements_to_correct_manually, measurements_to_fit_manually

    def calculate_thermal_conductivity_from_dir(self, dirs, re_evaluate_data, re_correct_data, do_correction_manually, do_evaluation_manually):

        for directory_path in dirs:
            '''
            #print(directory_path)
            #measurements_to_correct_manually, measurements_to_fit_manually = THS.correct_and_evaluate_measurement(
            #    directory_path=directory_path, re_evaluate_data=True, re_correct_data=False, do_correction_manually=True,
            #    do_evaluation_manually=False)
            '''
            print(directory_path)
            self.correct_and_evaluate_measurement(
                directory_path=directory_path, re_evaluate_data=re_evaluate_data, re_correct_data=re_correct_data,
                do_correction_manually=do_correction_manually,
                do_evaluation_manually=do_evaluation_manually)

            print('temp corr err set to 0')





if __name__ == '__main__':
    import pyvisa
    def get_dir(self):
        root_getdir = tk.Tk()
        # Hide the window
        root_getdir.attributes('-alpha', 0.0)
        root_getdir.attributes('-topmost', True)
        directory_path = filedialog.askdirectory(title='Select Directory with Measurements',
                                                 initialdir='Data/Conductivity Measurements',
                                                 parent=root_getdir)
        # root.withdraw()
        root_getdir.destroy()
        return directory_path

    rm = pyvisa.ResourceManager()
    THS = THS_Control(rm)

    # calculate thermal conductivity from a dir or file
    #directory_path = r'C:/Users/CoPhyLab Werkstatt/OneDrive/Desktop/TVAC PID/Data/Tests/Ice Particles 0'

    sample_names = [#'Dry LHS-1 0',
                    #'Dry LHS-1 1',
                    #'Dry TUBS 0',
                    #'FGB Glass',
                    #'Ice Particles 0',
                    'Icy LHS-1 0',
                    #'Icy LHS-1 1',
                    #'Icy LHS-1 2',
                    #'Mud Pie 0'
                    ]
    path = r'Data/Conductivity Measurements/'
    dirs = np.char.add(path, np.array(sample_names))
    THS.calculate_thermal_conductivity_from_dir(dirs, re_evaluate_data=False, re_correct_data=False,
                                                do_correction_manually=True, do_evaluation_manually=True)

