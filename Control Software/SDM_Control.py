# -*- coding: utf-8 -*-
"""
Created on Tue Sep 12 09:11:50 2023

@author: henni
"""

import time
import pyvisa
import pandas as pd
import numpy as np
import tkinter as tk


class SDM3065X:

    def __init__(self, resource_manager):
        self.device = None
        self.rm = resource_manager
        
        self.active = False
        self.scanner_card_active = False
        self.active_measurement = False
        
        self.scan_function = None
        
        self.AVAILABLE_CHANNELS = list(range(1, 17))
        self.AVAILABLE_SCAN_MODES = ['SCAN', 'STEP']
        self.AVAILABLE_MODES = ['DCV', 'DCI', 'ACV', 'ACI', '2W', '4W', 'CAP', 'FRQ', 'CONT', 'DIO', 'TEMP']
        self.AVAILABLE_RANGES = {
            'DCV': ['AUTO', '200MLV', '2V', '20V', '200V'],
            'DCI': ['2A'],
            'ACV': ['AUTO', '200MLV', '2V', '20V', '200V'],
            'ACI': ['2A'],
            '2W': ['AUTO', '200OHM', '2KOHM', '20KOHM', '200KOHM', '2MGOHM', '10MGOHM', '100MGOHM'],
            '4W': ['AUTO', '200OHM', '2KOHM', '20KOHM', '200KOHM', '2MGOHM', '10MGOHM', '100MGOHM'],
            'CAP': ['AUTO', '2NF', '20NF', '200NF', '2UF', '20UF', '200UF', '10000UF'],
            'FRQ': ['AUTO', '200MLV', '2V', '20V', '200V'],
            'CONT': [],
            'DIO': [],
            'TEMP': ['RTD', 'THER', 'UNIT']
        }
        self.AVAILABLE_SPEEDS = ['SLOW', 'FAST']
        self.AVAILABLE_LIMITS = ['HIGH', 'LOW']
        self.AVAILABLE_AZ_MODES = ['DCV', 'DCI', 'RES', 'FRES']
        
        # tkinter entrys for status/error
        self.output = None
        self.error_output = None
        
        # channel numbers for tvac measurements
        self.chan_ths_shunt_volt = 9
        self.chan_sample_holder = 11  # 1-12
        self.chan_exhaust = 10  # 1-12
        self.chan_ths_volt = 12  # 1-12
        self.chan_ths_curr = 13  # 13-16
        
        # return value to read measurements
        self.latest_tvac_values = None
        self.need_reset = None

    def start_device(self, output=None, error_output=None):
        if output is None:
            output = tk.Entry()
            print('SDM3065X-SC not connected to tkinter GUI output')
        if error_output is None:
            error_output = tk.Entry()
            print('SDM3065X-SC not connected to tkinter GUI error output')
        self.output = output
        self.error_output = error_output
        self.output.delete(0, tk.END)
        self.output.insert(0, 'Starting SDM3065X-SC')
        if not self.active:
            self.resources_list = self.rm.list_resources()
            if 'USB0::0xF4EC::0x1208::SDM36HCX7R0827::INSTR' not in self.resources_list:
                self.error_output.delete(0, tk.END)
                self.error_output.insert(0, f'SDM3065X-SC: Not found in active resources: {self.resources_list}. Please Connect device.')
                return
            try:
                time.sleep(0.5)
                self.device = self.rm.open_resource('USB0::0xF4EC::0x1208::SDM36HCX7R0827::INSTR')
                self.device.read_termination = '\n'
                self.device.write_termination = '\n'
                self.device.clear()
                self.device.write('SYSTem:PRESet')
            except:
                self.error_output.delete(0, tk.END)
                self.error_output.insert(0, 'SDM3065X-SC: Connection failed. Device not found.')
                self.stop_device()
                return
            for ii in range(3):
                time.sleep(0.5)
                try:
                    idn = self.device.query('*IDN?')
                    #print(idn)
                    if idn.find('SDM3065X-SC') != -1:
                        self.output.delete(0, tk.END)
                        self.output.insert(0, 'Connected.')
                        self.active = True
                        return
                except:
                    continue
            self.error_output.delete(0, tk.END)
            self.error_output.insert(0, 'SDM3065X-SC: Connection failed. IDN invalid.')
            self.stop_device() # stop device if request failed
                
    def stop_device(self):
        try:
            self.device.write('R?')
        except Exception as e:
            pass
            '''
            try:
                self.output.delete(0, tk.END)
                self.output.insert(0, f'Failed to clear reading buffer. {e}')
            except AttributeError:
                pass
            '''
        try:
            time.sleep(0.5)
            self.device.write('ABORt') # abort all measurements
        except Exception as e:
            pass
            '''
            try:
                self.output.delete(0, tk.END)
                self.output.insert(0, f'Failed to abort measurements. {e}')
            except AttributeError:
                pass
            '''
        try:
            time.sleep(0.5)
            self.device.write('ROUTe:STARt OFF') # stop scan
        except Exception as e:
            pass
            '''
            try:
                self.output.delete(0, tk.END)
                self.output.insert(0, f'Failed to stop scan. {e}')
            except AttributeError:
                pass
            '''
        try:
            time.sleep(0.5)
            self.device.write('ROUTe:SCAN OFF') # close scanner card
        except Exception as e:
            pass
            '''
            try:
                self.output.delete(0, tk.END)
                self.output.insert(0, f'Failed to close scanner card. {e}')
            except AttributeError:
                pass
            '''
        try:
            time.sleep(0.5)
            self.device.write('SYSTem:PRESet') # reset device to power up power up configuration
        except Exception as e:
            pass
            '''
            try:
                self.output.delete(0, tk.END)
                self.output.insert(0, f'Failed to reset device to power up configuration. {e}')
            except AttributeError:
                pass
            '''
        finally:
            time.sleep(0.5)
            try:
                self.device.close() # close device
                self.output.delete(0, tk.END)
                self.output.insert(0, 'Device closed')
            except AttributeError:
                pass
            self.active = False
            self.active_measurement = False
            print(pd.Timestamp('now').strftime('%X'), 'SDM disconnected')
        
    def start_scanner_card(self):
        if self.active and not self.scanner_card_active:
            try:
                self.device.write('ROUTe:SCAN ON')
                for ii in range(3):
                    time.sleep(0.5)
                    try:
                        scanner_card_status = self.device.query('ROUTe:SCAN?')
                        if scanner_card_status.strip()=='ON':
                            self.scanner_card_active = True
                            #print(f'Scanner card activated after {ii+1} trie(s)')
                            return
                        else:
                            self.scanner_card_active = False
                    except KeyboardInterrupt:
                        break
                    except:
                        #print(f'Scanner card status request failed {ii+1}/3 times', e)
                        continue
                self.stop_device() # stop device if request failed
            except:
                self.output.delete(0, tk.END)
                self.output.insert(0, 'Failed to start scanner card')
                pass
        else:
            self.error_output.delete(0, tk.END)
            self.error_output.insert(0, 'SDM3065X-SC inactive at start_scanner_card')
            raise Exception('SDM3065X-SC inactive')
        
    def stop_scanner_card(self):
        try:
            self.device.write('ROUTe:SCAN OFF')
            self.scanner_card_active = False
        except:
            self.error_output.delete(0, tk.END)
            self.error_output.insert(0, 'SDM3065X-SC failed to stop scanner card')
            raise Exception('SDM3065X-SC stop_scanner_card failed')
            
    def select_scan_function(self, scan_function='STEP'):
        if self.active and self.scanner_card_active:
            if scan_function in self.AVAILABLE_SCAN_MODES:
                self.scan_function = scan_function
                try:
                    time.sleep(0.5)
                    self.device.write(f'ROUTe:FUNC {scan_function}')
                    #print('Setting scan function')
                except:
                    self.output.delete(0, tk.END)
                    self.output.insert(0, 'Setting scan function failed')
                    pass
        else:
            self.error_output.delete(0, tk.END)
            self.error_output.insert(0, 'SDM3065X-SC inactive at select_scan_function')
            raise Exception('SDM3065X-SC inactive')
            
    def set_scan_delay(self, delay):
        if self.active and self.scanner_card_active:
            if isinstance(delay, (int, float)):
                for ii in range(3):
                    try:
                        time.sleep(0.5)
                        self.device.write(f'ROUTe:DELay {delay}')
                        time.sleep(0.5)
                        set_delay = self.device.query('ROUTe:DELay?')
                        if float(set_delay)==delay:
                            #print(f'Delay set correctly after {ii+1} trie(s)')
                            return
                    except:
                        #print(f'Setting scan delay failed {ii+1}/3 times', e)
                        continue
                self.output.delete(0, tk.END)
                self.output.insert(0, 'Failed to set scan delay')
                self.stop_device() # stop device if request failed
        else:
            self.error_output.delete(0, tk.END)
            self.error_output.insert(0, 'SDM3065X-SC inactive at set_scan_delay')
            raise Exception('SDM3065X-SC inactive')
            
    def set_scan_cycle_count_auto(self, status=''):
        if self.active and self.scanner_card_active:
            if status in ['', 'ON', 'OFF', 0, 1]:
                for ii in range(3):
                    time.sleep(0.5)
                    try:
                        self.device.write(f'ROUTe:COUNt:AUTO {status}')
                        return
                    except Exception as e:
                        print(f'Failed to set scan card cycle count {ii+1}/3 times', e)
                self.output.delete(0, tk.END)
                self.output.insert(0, 'Failed to set scan card cycle count auto')
            else:
                self.output.delete(0, tk.END)
                self.output.insert(0, f'Invalid set_scan_cycle_count_auto status {status}. Automatically setting to ON')
                self.set_scan_cycle_count_auto(status='ON')
        else:
            self.error_output.delete(0, tk.END)
            self.error_output.insert(0, 'SDM3065X-SC inactive at set_scan_cycle_count_auto')
            raise Exception('SDM3065X-SC inactive')
            
    def set_scan_cycle_count(self, count):
        if self.active and self.scanner_card_active:
            if isinstance(count, int) or (count in ['MIN', 'MAX', 'DEF']):
                for ii in range(3):
                    time.sleep(0.5)
                    try:
                        self.device.write(f'ROUTe:COUNt {count}')
                        time.sleep(0.5)
                        set_count = self.device.query('ROUTe:COUNt?')
                        if set_count.strip() == str(count):
                            return
                    except:
                        continue
                self.output.delete(0, tk.END)
                self.output.insert(0, 'Failed to set scan cycle count')
            else:
                self.output.delete(0, tk.END)
                self.output.insert(0, f'Invalid set_scan_cycle_count count {count}. Automatically setting to 1')
                self.set_scan_cycle_count(count=1)
        else:
            self.error_output.delete(0, tk.END)
            self.error_output.insert(0, 'SDM3065X-SC inactive at set_scan_cycle_count')
            raise Exception('SDM3065X-SC inactive')
            
    def set_active_channels(self, lower_channel_limit=1, higher_channel_limit=16):
        if self.active and self.scanner_card_active:
            if lower_channel_limit in self.AVAILABLE_CHANNELS and higher_channel_limit in self.AVAILABLE_CHANNELS:
                for ii in range(3):
                    try:
                        time.sleep(0.5)
                        self.device.write(f'ROUTe:LIMI:LOW {lower_channel_limit}')
                        time.sleep(0.5)
                        self.device.write(f'ROUTe:LIMI:HIGH {higher_channel_limit}')
                        time.sleep(0.5)
                        lower_limit = int(self.device.query('ROUte:LIMI:LOW?'))
                        if lower_limit != lower_channel_limit:
                            lower_limit_set = False
                        else:
                            lower_limit_set = True
                        time.sleep(0.5)
                        upper_limit = int(self.device.query('ROUte:LIMI:HIGH?'))
                        if upper_limit != higher_channel_limit:
                            upper_limit_set = False
                        else:
                            upper_limit_set = True
                        if lower_limit_set and upper_limit_set:
                            return
                        
                    except:
                        continue
                self.output.delete(0, tk.END)
                self.output.insert(0, 'Failed to set active channels')
                self.stop_device() # stop device if request failed
            else:
                self.output.delete(0, tk.END)
                self.output.insert(0, 'Selected channel limits not valid')
                pass
        else:
            self.error_output.delete(0, tk.END)
            self.error_output.insert(0, 'SDM3065X-SC inactive at set_active_channels')
            raise Exception('SDM3065X-SC inactive')
            
    def configure_measurement(self, channel, mode='DCV', range_='AUTO', speed='SLOW'):
        '''
        channel = [1, 16]
        mode = ['DCV', 'DCI', 'ACV', 'ACI', '2W', '4W', 'CAP', 'FRQ', 'CONT', 'DIO', 'TEMP']
        range_ = {
            'DCV': ['AUTO', '200MLV', '2V', '20V', '200V'],
            'DCI': ['2A'],
            'ACV': ['AUTO', '200MLV', '2V', '20V', '200V'],
            'ACI': ['2A'],
            '2W': ['AUTO', '200OHM', '2KOHM', '20KOHM', '200KOHM', '2MGOHM', '10MGOHM', '100MGOHM'],
            '4W': ['AUTO', '200OHM', '2KOHM', '20KOHM', '200KOHM', '2MGOHM', '10MGOHM', '100MGOHM'],
            'CAP': ['AUTO', '2NF', '20NF', '200NF', '2UF', '20UF', '200UF', '10000UF'],
            'FRQ': ['AUTO', '200MLV', '2V', '20V', '200V'],
            'CONT': [],
            'DIO': [],
            'TEMP': ['RTD', 'THER', 'UNIT']
        }
        speed = ['SLOW', 'FAST']
        '''
        if self.active and self.scanner_card_active:
            if channel not in self.AVAILABLE_CHANNELS:
                raise ValueError(f'Invalid channel {channel}. Available channels: {self.AVAILABLE_CHANNELS}')
            if mode not in self.AVAILABLE_MODES:
                raise ValueError(f'Invalid mode {mode}. Available modes: {self.AVAILABLE_MODES}')
            if range_ not in self.AVAILABLE_RANGES.get(mode, []):
                raise ValueError(f'Invalid range {range_} for mode {mode}. Available ranges: {self.AVAILABLE_RANGES.get(mode, [])}')
            if speed not in self.AVAILABLE_SPEEDS:
                raise ValueError(f'Invalid speed {speed}. Available speeds: {self.AVAILABLE_SPEEDS}')
    
            time.sleep(0.5)
            command = f'ROUTe:CHANnel {channel}, ON, {mode}, {range_}, {speed}'
            try:
                self.device.write(command)
            except Exception as e:
                self.output.delete(0, tk.END)
                self.output.insert(0, f'Failed to configure channel. {e}')
        else:
            self.error_output.delete(0, tk.END)
            self.error_output.insert(0, 'SDM3065X-SC: Inactive at configure_measurement')
            raise Exception('SDM3065X-SC inactive') 
            
    def set_autozero(self, mode='DCV', state='ON'):
        if self.active and self.scanner_card_active:
            if mode not in self.AVAILABLE_AZ_MODES:
                raise ValueError(f'Invlid mode {mode}. Available modes: [\'DCV\', \'DCI\', \'RES\', \'FRES\']')
            if state not in ['ON', 'OFF', 0, 1]:
                raise ValueError(f'Invlid state {state}. Available states: [\'ON\', \'OFF\', 0, 1]')
            try:
                self.device.write(f'ROUTe:{mode}:AZ {state}')
            except:
                self.stop_device() # stop device if request failed
        else:
            self.error_output.delete(0, tk.END)
            self.error_output.insert(0, 'SDM3065X-SC inactive at set_autozero')
            raise Exception('SDM3065X-SC inactive')
            
    def start_scan(self):
        if self.active and self.scanner_card_active:
            self.device.write('R?') # clear buffer
            while True:
                try:
                    time.sleep(0.5)
                    self.device.write('ROUTe:STARt ON') # start scan
                    time.sleep(0.5)
                    scan_status = self.device.query('ROUTe:STARt?')
                    if scan_status.strip() == 'ON':
                        time.sleep(3)
                        return
                except KeyboardInterrupt:
                    break
                except Exception as e:
                    print(f'STARt? query failed. {e}')
        else:
            self.error_output.delete(0, tk.END)
            self.error_output.insert(0, 'SDM3065X-SC inactive at start_scan')
            raise Exception('SDM3065X-SC inactive')     
            
    def stop_scan(self):
        try:
            self.device.write('ROUTe:STARt OFF') # stop scan
        except:
            self.output.delete(0, tk.END)
            self.output.insert(0, 'Failed to stop scan')
            
    def read_data(self, channel):
        if self.active and self.scanner_card_active:
            if channel in self.AVAILABLE_CHANNELS:
                try:
                    data = self.device.query(f'ROUTe:DATA? {channel}')
                    return data
                except Exception as error:
                    print(pd.Timestamp('now').strftime('%X'), f'Siglent read_data: {error}')
                    return None
        else:
            #self.error_output.delete(0, tk.END)
            #self.error_output.insert(0, 'SDM3065X-SC inactive at read_data')
            raise Exception('SDM3065X-SC inactive')
                
            
    def check_for_errors(self, count=1):
        if self.active:
            for i in range(count):
                try:
                    error = self.device.query('SYSTem:ERRor?')
                except KeyboardInterrupt as error:
                    raise KeyboardInterrupt()
                except Exception as error:
                    print(error)
                finally:
                    #self.error_output.delete(0, tk.END)
                    #self.error_output.insert(0, f'SDM3065X-SC: {error}')
                    pass
        else:
            #self.error_output.delete(0, tk.END)
            #self.error_output.insert(0, 'SDM3065X-SC inactive at check_for_errors')
            raise Exception('SDM3065X-SC inactive')
            
    def start_tvac_measuring(self, output, error_output):
        self.output = output
        self.error_output = error_output
        
        if self.active:
            self.output.delete(0, tk.END)
            self.output.insert(0, 'Setting up measurement...')
            
            self.start_scanner_card()
            
            self.select_scan_function(scan_function='SCAN') # measure one channel at a time, then step to next one
            self.set_scan_delay(0.2) # set delay between scans in s
            self.set_scan_cycle_count_auto(status='ON') # scan channels circularly until scan is ended
            self.set_active_channels(lower_channel_limit=9, higher_channel_limit=12) # channel 13 for current

            self.configure_measurement(channel=self.chan_ths_shunt_volt, mode='DCV', range_='20V', speed='SLOW')
            self.configure_measurement(channel=self.chan_sample_holder, mode='2W', range_='2KOHM', speed='SLOW')
            self.configure_measurement(channel=self.chan_exhaust, mode='2W', range_='2KOHM', speed='SLOW')
            self.configure_measurement(channel=self.chan_ths_volt, mode='DCV', range_='2V', speed='SLOW')

            self.set_autozero(mode='RES', state='ON')
            self.set_autozero(mode='DCV', state='ON')

            self.start_scan()
            
            self.output.delete(0, tk.END)
            self.output.insert(0, 'Measurement active!')
            
            self.active_measurement = True
            
            starting_time = pd.Timestamp.now()
            latest_time = starting_time
            invalid_feedback_counter = 0
            while self.active_measurement and self.active:
                if pd.Timestamp.now()-latest_time < pd.Timedelta(4, 's'):
                    continue
                try:
                    ths_shunt_voltage = self.read_data(channel=self.chan_ths_shunt_volt)
                    sample_holder_temp = self.read_data(channel=self.chan_sample_holder)
                    exhaust_temp = self.read_data(channel=self.chan_exhaust)
                    ths_voltage = self.read_data(channel=self.chan_ths_volt)
                    print(pd.Timestamp('now').strftime('%X'), 'SDM Feedback:', sample_holder_temp, exhaust_temp, ths_voltage, ths_shunt_voltage)
                    current_time = pd.Timestamp.now()

                    if sample_holder_temp is None and exhaust_temp is None and ths_voltage is None:
                        invalid_feedback_counter += 1
                        if invalid_feedback_counter >= 3:
                            self.need_reset = True
                    else:
                        self.need_reset = False

                    values = [current_time, sample_holder_temp, exhaust_temp, ths_voltage, ths_shunt_voltage]
                    for ii, value in enumerate(values):
                        if ii != 0:
                            try:
                                value = float(value.split()[0])
                                if value == 0.0:
                                    value = np.nan
                            except:
                                value = np.nan
                            finally:
                                values[ii] = value
                    self.latest_tvac_values = values
                    
                    latest_time = pd.Timestamp.now()      
                except Exception as e:
                    self.output.delete(0, tk.END)
                    self.output.insert(0, f'Reading data failed. {e}')
                    break
                
            self.output.delete(0, tk.END)
            self.output.insert(0, 'Measurement stopped.')
            
            self.active_measurement = False
            self.stop_device()
        else:
            self.error_output.delete(0, tk.END)
            self.error_output.insert(0, 'SDM3065X-SC: Inactive!')
        
        
    def get_latest_measurement(self):
        # self.latest_tvac_values = [time, sample_holder_temp, exhaust_temp, ths_voltage, ths_current]
        if self.latest_tvac_values is not None:
            return self.latest_tvac_values
        else:
            return None

