# -*- coding: utf-8 -*-
"""
Class for controlling temperature of TVAC.

Uses Siglent Digital Multimeter (SDM) to read temperatures and 
USB_Relay to control heating and cooling.

Uses class_PID for PID logic to enable smooth temperature changes and autotuning.

@author: Henning Wache

based on initial code by 
@author: Moritz Goldmann
"""

### Packages for calculations and vizualizations
import tkinter as tk
import time
import pandas as pd
import numpy as np
import scipy as sc
from sklearn.linear_model import LinearRegression


### Packages for temperature control algorithm
from class_PID import class_PID
PID_obj = class_PID()

def temp_from_pt1000(R0=1000.0):
    # interpolation function for Pt-1000 based con Callendar van Dusen equation
    def callendar_van_dusen(temp_C, R0):
        A = 3.9083e-3  # 1/°C
        B = -5.775e-7  # 1/(°C)^2
        C = -4.183E-12  # 1/(°C)^3

        mask1 = (0 <= temp_C) & (temp_C <= 661)
        mask2 = (-200 <= temp_C) & (temp_C < 0)
        R_T = np.where(mask1, R0 * (1 + A * temp_C + B * temp_C ** 2), R0)
        R_T = np.where(mask2, R0 * (1 + A * temp_C + B * temp_C ** 2 + C * (temp_C - 100) * temp_C ** 3), R_T)
        if not (mask1 | mask2).all():
            raise ValueError('Temperature out of range of Callendar-van-Dusen Equation!')
        return R_T

    temperatures_C = np.arange(-200, 616, 0.01)
    temperatures_K = temperatures_C + 273.15
    resistances = callendar_van_dusen(temperatures_C, R0)
    interp_func = sc.interpolate.interp1d(x=resistances, y=temperatures_K)
    return interp_func

class TVAC_Control:
    def __init__(self):
        self.running = False  # indicates TVAC_Control status
        self.end = False  # command variable to break while loop and stop devices
        self.activate_tvac_control = False # indicates if connection to devices has been established correctly
        self.create_new_file = False  # bool to initialise creation of new file
        self.filename = None
        ### start/stop heating
        self.START_cooling = False  # command variable to start cooling
        self.STOP_cooling = False  # command variable to start cooling
        self.START_heating = False  # command variable to start heating
        self.STOP_heating = False  # command variable to stop heating
        self.cooling_active = False  # indicates cooling status
        self.heating_active = False  # indicates heating status
        self.cooling_active_relay = False # indicates cooling status in terms of relay open/closed
        self.heating_active_relay = False # indicates heating status in terms of relay open/closed
        
        ### USB Relay channels
        self.channels_heating = [8, 9]  # [5,6,7,8]
        self.channels_cooling = [6, 7]  # [1,2,3,4]
        self.channel_heating = self.channels_heating[0]  # initial value for heating channel
        self.channel_cooling = self.channels_cooling[0]  # initial value for cooling channel
        self.channel_switch_time_heating = pd.Timestamp('now')
        self.channel_switch_time_cooling = pd.Timestamp('now')
        
        ### Devices
        self.USB_Relay = None
        self.SDM = None # Siglent Digital Multimeter
        self.latest_feedback = None
        self.reset_SDM = False
        self.get_pt1000_sample_holder_temp = temp_from_pt1000(R0=1000.785)  # pt1000 temp(res) interpolation, calibrated in ice water with std: 0.005
        self.get_pt1000_exhaust_temp = temp_from_pt1000(R0=1002.11)  # pt1000 temp(res) interpolation, calibrated in ice water
        
        ### Parameters for PID Calculations
        self.SET_target_temp = False  # command variable to set target temperature
        self.target_temp = -1  # initial target temperature
        self.PID_active = False  # indicates heating mode
        self.START_PID = False  # command variable to start pid heating mode
        self.STOP_PID = False  # command variable to stop pid heating mode
        self.SET_PID = False  # command variable to set PID values
        self.PID_cycle_active = False  # indicates active PID calculations
        self.pid_start_time = pd.Timestamp.now() # initial time for PID calculations
        self.time_delta = pd.Timedelta(3, 'min') # initial time interval for PID calc (integral/derivative)
        self.SET_timedelta = False
        self.proportional = 0  # initial proportional parameter
        self.integral = 0  # initial integral parameter
        self.derivative = 0  # initial derivative parameter
        self.PID_time_interval = pd.Timedelta(2, 'min') # initial time interval for PID heating/cooling cycle
        self.SET_PID_time_interval = False
        self.PID_min_rel_cooling_time = 0  # min relative time LN2 valve should be open each PID cycle
        self.PID_max_rel_cooling_time = 1  # max relative time LN2 valve should be open each PID cycle
        self.SET_PID_MIN_REL_COOLING_TIME = False
        self.SET_PID_MAX_REL_COOLING_TIME = False
        self.relative_heating_time = 0  # initial relative time to heat 
        self.relative_cooling_time = 0  # initial relative time to heat
        self.autotuning_complete = False
        self.failsave_overflow_ratio = 0.01  # % of data acceptable at LN2 temp to avoid exhaust overflow
        self.SET_FAILSAVE_OVERLOW_RATIO = False

        self.heating_rate = 0.60  # initial rate in kelvin per second
        self.cooling_rate = 0.11  # initial rate in kelvin per second
        self.temp_okay = False


    def start_tvac_control(self, SDM, USB_Relay, output, error_output, input_target_temp, input_PID,
                           input_time_delta, input_PID_time_interval, input_PID_min_rel_cooling_time,
                           input_PID_max_rel_cooling_time, input_failsave_overflow_ratio):
        self.SDM = SDM
        self.USB_Relay = USB_Relay
        self.output = output
        self.error_output = error_output
        if not self.SDM.active:
            self.error_output.delete(0, tk.END)
            self.error_output.insert(0, 'TVAC_Control: Activate SDM first!')
            return 
        # start devices and allow to go into main loop if feedback is valid
        self.end = False
        if not self.running:
            self.running = True
            # put back into try statement below if problems with USBRelay are fixed
            self.activate_tvac_control = True
            try:
                self.USB_Relay.start_device()
                self.output.delete(0, tk.END)
                self.output.insert(0, 'Connecting ...')
            except Exception as error:
                self.error_output.delete(0, tk.END)
                self.error_output.insert(0, str(error))
                #self.end = True

        if not self.end:
            if self.activate_tvac_control:
                self.output.delete(0, tk.END)
                self.output.insert(0, 'TVAC connected!')

                input_PID.delete(0, tk.END)
                input_PID.insert(0, f"{self.proportional:.3g},{self.integral:.3g},{self.derivative:.3g}")

                input_time_delta.delete(0, tk.END)
                input_time_delta.insert(0, self.time_delta.total_seconds()/60)

                input_PID_time_interval.delete(0, tk.END)
                input_PID_time_interval.insert(0, self.PID_time_interval.total_seconds()/60)

                input_PID_min_rel_cooling_time.delete(0, tk.END)
                input_PID_min_rel_cooling_time.insert(0, self.PID_min_rel_cooling_time)

                input_PID_max_rel_cooling_time.delete(0, tk.END)
                input_PID_max_rel_cooling_time.insert(0, self.PID_max_rel_cooling_time)

                input_failsave_overflow_ratio.delete(0, tk.END)
                input_failsave_overflow_ratio.insert(0, self.failsave_overflow_ratio)
                # create file to save data
                start_time = pd.Timestamp.now()
                self.filename = start_time.strftime('%Y-%m-%d-%H-%M-%S') + "_TVAC_Control"
                self.write_to_file(init=True)
                
                # main loop
                while True: 
                    # stop USB Relay when end was activated
                    if self.end:
                        try:    
                            self.output.delete(0, tk.END)
                            self.output.insert(0, 'TVAC disconnected!')
                        except RuntimeError:
                            pass
                        finally:
                            print(pd.Timestamp('now').strftime('%X'), 'TVAC_Control disconnected')
                        try:
                            self.USB_Relay.close_all_channels()
                        except Exception as error:
                            print(error)
                        self.running = False
                        break

                    # set new target temp from gui input
                    if self.SET_target_temp == True:
                        self.SET_target_temp = False
                        try:
                            self.target_temp = float(input_target_temp.get())
                        except Exception as error:
                            self.target_temp = -1
                        print(pd.Timestamp('now').strftime('%X'), 'setting target temperature', format(self.target_temp, '.2f'))
                        self.output.delete(0, tk.END)
                        self.output.insert(0, 'New target temp set!')

                    if self.SET_timedelta == True:
                        try:
                            self.time_delta = pd.Timedelta(float(input_time_delta.get()), 'min')
                        except Exception as error:
                            print(pd.Timestamp('now').strftime('%X'), 'Setting time_delta:', error)
                        print(pd.Timestamp('now').strftime('%X'), 'setting time_delta', self.time_delta)
                        self.output.delete(0, tk.END)
                        self.output.insert(0, 'New time_delta set!')
                        self.SET_timedelta = False

                    if self.SET_PID_time_interval == True:
                        try:
                            self.PID_time_interval = pd.Timedelta(float(input_PID_time_interval.get()), 'min')
                        except Exception as error:
                            print(pd.Timestamp('now').strftime('%X'), 'Setting PID_time_interval:', error)
                        print(pd.Timestamp('now').strftime('%X'), 'setting PID_time_interval', self.PID_time_interval)
                        self.output.delete(0, tk.END)
                        self.output.insert(0, 'New PID_time_interval set!')
                        self.SET_PID_time_interval = False

                    if self.SET_PID_MIN_REL_COOLING_TIME == True:
                        try:
                            self.PID_min_rel_cooling_time = float(input_PID_min_rel_cooling_time.get())
                        except Exception as error:
                            print(pd.Timestamp('now').strftime('%X'), 'Setting PID_min_cooling_time', error)
                        self.output.delete(0, tk.END)
                        self.output.insert(0, 'New PID_min_cooling_time set!')
                        self.SET_PID_MIN_REL_COOLING_TIME = False
                    if self.SET_PID_MAX_REL_COOLING_TIME == True:
                        try:
                            self.PID_max_rel_cooling_time = float(input_PID_max_rel_cooling_time.get())
                        except Exception as error:
                            print(pd.Timestamp('now').strftime('%X'), 'Setting PID_max_cooling_time', error)
                        self.output.delete(0, tk.END)
                        self.output.insert(0, 'New PID_max_cooling_time set!')
                        self.SET_PID_MAX_REL_COOLING_TIME = False
                        
                    if self.SET_FAILSAVE_OVERLOW_RATIO == True:
                        try:
                            self.failsave_overflow_ratio = float(input_failsave_overflow_ratio.get())
                        except Exception as error:
                            print(pd.Timestamp('now').strftime('%X'), 'Setting exhaust overflow ratio', error)
                        self.output.delete(0, tk.END)
                        self.output.insert(0, 'New exhaust overflow ratio set!')
                        self.SET_FAILSAVE_OVERLOW_RATIO = False
                        
                    # write all data to file
                    self.write_to_file()
                    
                    ### control commands
                    # temperature control commands will only be sent if each is not active already to not overflow devices
                    if self.START_cooling == True and self.cooling_active == False:
                        print(pd.Timestamp('now').strftime('%X'),'START cooling')
                        try:
                            self.USB_Relay.open_channel(self.channel_cooling)
                        except Exception as error:
                            print(error)
                        self.cooling_active = True
                        self.START_cooling=False
                    if self.STOP_cooling == True and self.cooling_active == True:
                        print(pd.Timestamp('now').strftime('%X'),'STOP cooling')
                        try:
                            self.USB_Relay.close_channel(self.channel_cooling)
                        except Exception as error:
                            print(error)
                        self.cooling_active = False
                        self.STOP_cooling = False
                    if self.START_heating == True and self.heating_active == False:
                        print(pd.Timestamp('now').strftime('%X'),'START heating')
                        try:
                            self.USB_Relay.open_channel(self.channel_heating)
                        except Exception as error:
                            print(error)
                        self.heating_active = True
                        self.START_heating = False
                    if self.STOP_heating == True and self.heating_active == True:
                        print(pd.Timestamp('now').strftime('%X'),'STOP heating')
                        try:
                            self.USB_Relay.close_channel(self.channel_heating)
                        except Exception as error:
                            print(error)
                        self.heating_active = False
                        self.STOP_heating = False

                    # set new PID values from gui input
                    if self.SET_PID == True:
                        self.SET_PID = False
                        try:
                            PID = str(input_PID.get()).split(',')
                            PID = np.array(PID, dtype=np.float64)
                            print(pd.Timestamp('now').strftime('%X'),'setting PID', PID)
                            self.output.delete(0, tk.END)
                            self.output.insert(0, f'New PID set!')
                            self.proportional = float(PID[0])
                            self.integral = float(PID[1])
                            self.derivative = float(PID[2])
                        except Exception as error:
                            print(pd.Timestamp('now').strftime('%X'),' Error while setting PID', error)
                            self.proportional = 0
                            self.integral = 0
                            self.derivative = 0
                        
                    # start or continue to run PID_heating
                    if self.START_PID == True or self.PID_active:
                        self.START_PID = False
                        self.PID_active = True
                        self.PID_heating()
                    # stop PID_heating
                    if self.STOP_PID == True:
                        self.STOP_PID = False
                        self.PID_active = False
                        class_PID.end_PID(PID_obj, end=True)

            # stop all devices if connection to devices failed        
            else:
                try:
                    self.output.delete(0, tk.END)
                    self.output.insert(0, 'TVAC_Control connection failed!')
                except RuntimeError:
                    pass
                finally:
                    print(pd.Timestamp('now').strftime('%X'), 'TVAC_Control connection failed')
                try:
                    self.USB_Relay.close_all_channels()
                except Exception as error:
                    print(error)
                self.running = False
        # skip loop if end was activated and stop all devices
        else: 
            try:    
                self.output.delete(0, tk.END)
                self.output.insert(0, 'TVAC_Control stopped!')
            except RuntimeError:
                pass
            finally:
                print(pd.Timestamp('now').strftime('%X'), 'TVAC_Control stopped')
            try:
                self.USB_Relay.close_all_channels()
            except Exception as error:
                print(error)
            self.heating_active = False
            self.cooling_active = False
            self.running = False
            self.end = False

    def write_to_file(self, init=False):
        # initialize file with header if needed
        if init:
            header = ['time', 'sample_holder_res', 'sample_holder_temp', 'exhaust_res', 'exhaust_temp', 'target_temp',
                    'cooling_active', 'heating_active', 'proportional', 'integral', 'derivative']
            with open("Data/" + self.filename + '.txt', "a+") as f:
                f.write(header[0])
                for value in header[1:]:
                    f.write(',')
                    f.write(str(value))
                f.write('\n')
        else:
            time.sleep(0.75)
            # get feedback from devices and print in file if valid
            feedback = self.SDM.get_latest_measurement()
            if feedback is None:
                return
            if self.latest_feedback is not None:
                if feedback[0] < self.latest_feedback[0]+pd.Timedelta(0.75, 's'):
                    return
            self.latest_feedback = feedback

            feedback_relay = self.USB_Relay.get_channel_status()
            if feedback is not None:
                time_value = feedback[0]
                sample_holder_res = feedback[1]
                exhaust_res = feedback[2]

                try:
                    sample_holder_temp = self.get_pt1000_sample_holder_temp(sample_holder_res)
                except:
                    sample_holder_temp = np.nan
                try:
                    exhaust_temp = self.get_pt1000_exhaust_temp(exhaust_res)
                except:
                    exhaust_temp = np.nan
                try:
                    cooling_active = feedback_relay[f'Channel {self.channel_cooling}']
                    heating_active = feedback_relay[f'Channel {self.channel_heating}']
                except Exception as error:
                    print(pd.Timestamp('now').strftime('%X'), error)
                    cooling_active = np.nan
                    cooling_active = np.nan

                if time_value==np.nan or sample_holder_temp==np.nan or exhaust_temp==np.nan:
                    print(pd.Timestamp('now').strftime('%X'),'Invalid device feedback found! Skipping values.')
                    return

                
                self.latest_feedback_time = time_value
                try:
                    self.cooling_active_relay = bool(cooling_active)
                    self.heating_active_relay = bool(heating_active)
                except Exception as error:
                    print(error)
                self.sample_holder_temp = sample_holder_temp
                self.exhaust_temp = exhaust_temp
                # print(pd.Timestamp('now').strftime('%X'), 'device feedback: ', feedback, feedback_relay)
                # format values
                time_value = time_value.strftime('%Y-%m-%d %H:%M:%S')
                sample_holder_temp = format(float(self.sample_holder_temp), '.3f')
                exhaust_temp = format(float(self.exhaust_temp), '.3f')
                target_temp = format(self.target_temp, '.3f')
                try:
                    cooling_active_relay = int(self.cooling_active_relay)
                    heating_active_relay = int(self.heating_active_relay)
                except:
                    cooling_active_relay = np.nan
                    heating_active_relay = np.nan
                proportional = format(self.proportional, '.3g')
                integral = format(self.integral, '.3g')
                derivative = format(self.derivative, '.3g')
                values = [time_value, sample_holder_res, sample_holder_temp, exhaust_res, exhaust_temp, target_temp,
                          cooling_active_relay, heating_active_relay, proportional, integral, derivative]
                with open("Data/" + self.filename + '.txt', "a+") as f:
                    f.write(values[0])
                    for value in values[1:]:
                        f.write(',')
                        f.write(str(value))
                    f.write('\n')
                self.output.delete(0, tk.END)
                self.output.insert(0, pd.Timestamp('now').strftime('%X') + ' Data saved!')
    
    def PID_heating(self, target_temp=None):
        ### logic for PID heating mode using functions from class_PID
        if self.STOP_PID:
            return
        self.running = True
        if self.end==True:
            class_PID.end_PID(PID_obj, end=True)
            return
        else:
            class_PID.end_PID(PID_obj, end=False)

        # read data from file
        data = pd.read_csv("Data/" + self.filename + '.txt', header=0)
        data = data.dropna()
        datetimes = np.array(data['time'].values, dtype='datetime64[s]')
        temperatures = np.array(data['sample_holder_temp'])

        # data copy for failsave in case of nitrogen overflow, stop pid if exhaust temp too long too cold
        data['time'] = pd.to_datetime(data['time'])
        data = data.dropna()
        data_failsave = data[data['time'] >= data['time'].iloc[-1]-self.PID_time_interval]
        exhaust_box_full_count = (data_failsave['exhaust_temp'] <= 78).sum()  # with threshold
        if exhaust_box_full_count >= self.failsave_overflow_ratio * data_failsave.shape[0]:
            self.stop_cooling()
        # failsave for Siglent malfunctioning, if no data is available, stop PID
        if data_failsave['sample_holder_temp'].empty or data_failsave['exhaust_temp'].empty:
            self.stop_PID()
            self.error_output.delete(0, tk.END)
            self.error_output.insert(0, 'WARNING: PID STOPPED, NO DATA AVAILABLE!')
            print(pd.Timestamp('now').strftime('%X'), 'Error: PID STOPPED, NO DATA AVAILABLE!')
            return
        if target_temp is not None:
            self.target_temp = target_temp
        if self.target_temp==-1:
            self.error_output.delete(0, tk.END)
            self.error_output.insert(0, "Invalid target temperature")
            print(pd.Timestamp('now').strftime('%X'), 'Error: Target Temperature -1 not valid')
            self.STOP_PID = True
            return
        PID_obj.PID = [float(self.proportional), float(self.integral), float(self.derivative)]
        PID_obj.time_delta = self.time_delta
        PID_obj.target_temp = self.target_temp
        PID_obj.min_relative_cooling_time = self.PID_min_rel_cooling_time
        PID_obj.max_relative_cooling_time = self.PID_max_rel_cooling_time
        # if PID-cycle is not active yet, use PID_control to get relative times and start heating if not zero
        if not self.PID_cycle_active:
            try:
                self.relative_heating_time, self.relative_cooling_time = class_PID.PID_control(PID_obj, datetimes, temperatures)
            except TimeoutError as error:
                print(pd.Timestamp('now').strftime('%X'), error)
                return
            except Exception as error:
                print(pd.Timestamp('now').strftime('%X'), 'TVAC_Control.PID_heating: ', error)
                #self.end = True
            #print(pd.Timestamp('now').strftime('%X'),'new time set:', self.relative_heating_time, self.relative_cooling_time)
            self.pid_start_time = pd.Timestamp.now()
            self.PID_cycle_active = True
            if self.relative_heating_time > 0.0:
                self.start_heating()
            if self.relative_cooling_time > 0.0 and exhaust_box_full_count <= self.failsave_overflow_ratio * data_failsave.shape[0]:
                self.start_cooling()
            print(pd.Timestamp('now').strftime('%X'), 'new PID cycle:', round(self.relative_heating_time, 3), round(self.relative_cooling_time, 3), PID_obj.PID)
        # if PID-cycle is active, check if relative heating time for the given interval was reached, stop heating if True.
        # If complete interval is finished, stop cycle so a new one can begin
        if self.PID_cycle_active:
            now = pd.Timestamp.now()
            if now >= self.pid_start_time + self.relative_heating_time * self.PID_time_interval:
                if self.relative_heating_time == 1.0:
                    self.start_heating() # do not stop if full heating power is required
                else:
                    self.stop_heating()
            if now >= self.pid_start_time + self.relative_cooling_time * self.PID_time_interval:
                if self.relative_cooling_time == 1.0 and exhaust_box_full_count <= self.failsave_overflow_ratio * data_failsave.shape[0]:
                    self.start_cooling() # do not stop if full cooling power is required but stop if exhaust gets too cold
                else:
                    self.stop_cooling()
            if now >= self.pid_start_time + self.PID_time_interval:
                self.PID_cycle_active = False
        #print(pd.Timestamp('now').strftime('%X'),'PID', PID_obj.PID, ' heating time', self.relative_heating_time, ' cooling time', self.relative_cooling_time)

    def PID_autotuning(self, PID_Entry, target_temp_entry):
        '''
        autotunes system with rough simulation based on target_temp, time_delta and system response (see class_PID)
        error_output and PID_string are Entrys of GUI
        '''
        self.autotuning_complete = False
        target_temp = float(target_temp_entry.get())
        PID_Entry.delete(0, tk.END)
        PID_Entry.insert(0, f'Autotuning for {target_temp:.3f} K...')
        self.running = True
        if self.end == True:
            class_PID.end_PID(PID_obj, end=True)
        else:
            class_PID.end_PID(PID_obj, end=False)
        # extract data from datafile to use in class_PID
        data = pd.read_csv("Data/" + self.filename + '.txt', header=0)
        data = data.dropna()
        datetimes = np.array(data['time'].values, dtype='datetime64[s]')
        temperatures = np.array(data['sample_holder_temp'])
        PID_obj.target_temp = target_temp
        PID_obj.time_delta = self.time_delta
        PID_obj.heating_rate = self.heating_rate
        PID_obj.cooling_rate = self.cooling_rate
        PID_obj.min_relative_cooling_time = self.PID_min_rel_cooling_time
        PID_obj.max_relative_cooling_time = self.PID_max_rel_cooling_time
        # try autotuning and catch errors
        try:
            opt_PID = class_PID.PID_autotune(PID_obj, datetimes, temperatures)
        except TimeoutError as error:
            print(pd.Timestamp('now').strftime('%X'), 'TVAC_Control.PID_autotuning ', error)
            PID_Entry.delete(0, tk.END)
            self.error_output.delete(0, tk.END)
            self.error_output.insert(0, error)
            return
        except Exception as error:
            PID_Entry.delete(0, tk.END)
            self.error_output.delete(0, tk.END)
            self.error_output.insert(0, error)
            print(pd.Timestamp('now').strftime('%X'), 'TVAC_Control.PID_autotuning ', error)
            self.proportional = 0
            self.integral = 0
            self.derivative = 0
            return
        self.proportional = float(opt_PID[0])
        self.integral = float(opt_PID[1])
        self.derivative = float(opt_PID[2])
        # show new PID in gui
        PID_Entry.delete(0, tk.END)
        PID_Entry.insert(0, f"{self.proportional:.3g},{self.integral:.3g},{self.derivative:.3g}")
        self.autotuning_complete = True
        
    
    def start_cooling(self):
        if self.running == True:
            self.START_cooling = True
            self.STOP_cooling = False
    def stop_cooling(self):
        if self.running == True:
            self.STOP_cooling = True
            self.START_cooling = False

    def start_heating(self):
        if self.running == True:
            self.START_heating = True
            self.STOP_heating = False

    def stop_heating(self):
        if self.running == True:
            self.STOP_heating = True
            self.START_heating = False

    def set_target_temp(self):
        if self.running == True:
            self.SET_target_temp = True

    def set_PID(self):
        if self.running == True:
            self.SET_PID = True

    def set_timedelta(self):
        if self.running == True:
            self.SET_timedelta = True

    def set_PID_time_interval(self):
        if self.running == True:
            self.SET_PID_time_interval = True

    def set_PID_min_rel_cooling_time(self):
        if self.running == True:
            self.SET_PID_MIN_REL_COOLING_TIME = True

    def set_PID_max_rel_cooling_time(self):
        if self.running == True:
            self.SET_PID_MAX_REL_COOLING_TIME = True

    def set_failsave_overlow_ratio(self):
        if self.running == True:
            self.SET_FAILSAVE_OVERLOW_RATIO = True

    def start_PID(self):
        if self.running == True:
            self.START_PID = True
            self.STOP_cooling = False
            self.STOP_heating = False
            self.STOP_PID = False
            class_PID.end_PID(PID_obj, end=False)

    def stop_PID(self):
        if self.running == True:
            self.STOP_heating = True
            self.STOP_cooling = True
            self.STOP_PID = True
            class_PID.end_PID(PID_obj, end=True)
    
    def stop_tvac_control(self):
        self.USB_Relay.stop_device()
        self.end = True
        self.running = False

    def reset_sdm(self, SDM):
        self.SDM = SDM


    def linear_regression(self, x, y):
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


    def check_tvac_control(self):
        """
        checks if temperature values of data exceed a maximum deviation.
        min_ratio_in_interval allows for some values to lie outside (data spikes, small fluctuations)
        """
        if self.running:
            # get data from last 60 min
            try:
                data = pd.read_csv("Data/" + self.filename + '.txt', header=0)
            except TypeError:
                return
            data = data.dropna()
            data['time'] = pd.to_datetime(data['time'])
            data = data.dropna()
            try:
                data = data[data['time'] >= data['time'].iloc[-1]-pd.Timedelta(60, 'min')]
            except IndexError:
                # return if not enough data is available
                return
            ### check if temperature is stable around the current mean value
            self.temp_okay = False
            max_temp_deviation = 0.1
            min_ratio_in_interval = 0.95
            data['temperature_okay'] = (data['sample_holder_temp'] <= self.target_temp + max_temp_deviation) & (
                        data['sample_holder_temp'] >= self.target_temp - max_temp_deviation)
            if data['temperature_okay'].sum() >= min_ratio_in_interval * data.shape[0]:
                self.temp_okay = True

            ### calculate heating/cooling rates and check relay
            # group data to active heating/cooling intervals
            data['group_heating'] = (data['heating_active'] != data['heating_active'].shift(1)).cumsum()
            data['group_cooling'] = (data['cooling_active'] != data['cooling_active'].shift(1)).cumsum()
            heating_active_groups = data[data['heating_active'] == 1]
            cooling_active_groups = data[data['cooling_active'] == 1]
            heating_intervals = heating_active_groups.groupby('group_heating')['time'].agg(['min', 'max'])
            cooling_intervals = cooling_active_groups.groupby('group_cooling')['time'].agg(['min', 'max'])

            now = pd.Timestamp('now').strftime('%X')

            max_heating_rate = 0
            for ii in range(heating_intervals.shape[0]):
                min, max = heating_intervals.iloc[ii]
                if max - min >= pd.Timedelta(30, 'sec'):
                    data_interval = data[(data['time'] >= min) & (data['time'] <= max)].copy()
                    data_interval['seconds'] = (data_interval['time'] - data_interval['time'].iloc[0]).dt.total_seconds()
                    data_interval = data_interval.dropna()
                    slope, intercept, slope_err, intercept_err = self.linear_regression(data_interval['seconds'],
                                                                                   data_interval['sample_holder_temp'])
                    if slope > max_heating_rate:
                        max_heating_rate = slope

                    # if temperature drops although heating active, switch relay channel
                    if (slope <= 0 and ii == heating_intervals.shape[0]-1
                            and self.channel_switch_time_heating >= pd.Timestamp('now') - pd.Timedelta(1, 'min')):
                        idx_heating = self.channels_heating.index(self.channel_heating)
                        new_idx_heating = (idx_heating + 1) % len(self.channels_heating)  # got to next channel
                        self.channel_heating = self.channels_heating[new_idx_heating]
                        self.channel_switch_time_heating = pd.Timestamp('now')

                        self.error_output.delete(0, tk.END)
                        self.error_output.insert(0, f' {now} Relay {self.channels_heating[idx_heating]} (heating) failed!')

            # set new heating rate for PID autotuning
            if max_heating_rate != 0:
                self.heating_rate = max_heating_rate

            max_cooling_rate = 0
            for ii in range(cooling_intervals.shape[0]):
                min, max = cooling_intervals.iloc[ii]
                if max - min >= pd.Timedelta(30, 'sec'):
                    data_interval = data[(data['time'] >= min) & (data['time'] <= max)].copy()
                    data_interval['seconds'] = (data_interval['time'] - data_interval['time'].iloc[0]).dt.total_seconds()
                    data_interval = data_interval.dropna()
                    slope, intercept, slope_err, intercept_err = self.linear_regression(data_interval['seconds'],
                                                                                   data_interval['sample_holder_temp'])
                    if abs(slope) > max_cooling_rate:
                        max_cooling_rate = abs(slope)

                    # if temperature rises although cooling active, switch relay channel
                    if (slope >= 0 and ii == cooling_intervals.shape[0]-1
                            and self.channel_switch_time_cooling >= pd.Timestamp('now') - pd.Timedelta(1, 'min')):
                        idx_cooling = self.channels_cooling.index(self.channel_cooling)
                        new_idx_cooling = (idx_cooling + 1) % len(self.channels_cooling)  # got to next channel index
                        self.channel_cooling = self.channels_cooling[new_idx_cooling]
                        self.channel_switch_time_cooling = pd.Timestamp('now')
                        self.error_output.delete(0, tk.END)
                        self.error_output.insert(0, f'{now} Relay {self.channels_cooling[idx_cooling]} (cooling) failed!')
            # set new cooling rate for PID autotuning
            if max_cooling_rate != 0:
                self.cooling_rate = max_cooling_rate























