# -*- coding: utf-8 -*-
"""
Created on Mon Dec  4 15:03:47 2023

@author: henni
"""

import serial
import time


class ArduinoRelay():

    def __init__(self):
        self.port = "COM3"
        self.active = False
        self.ser = None
        self.relay_channels = [6, 7, 8, 9]
        self.channel_status = {}
        for channel_num in self.relay_channels:
            self.channel_status[f'Channel {channel_num}'] = 0

    def get_feedback(self):
        feedback = None
        self.ser.reset_input_buffer()
        self.ser.write(str.encode("S"))
        for i in range(3):
            feedback = self.ser.readline().decode('utf-8')
            if feedback.startswith("Status"):
                return feedback
        '''
        feedback = self.ser.readline().decode("utf-8")
        if feedback.startswith("Status:") and len(feedback) == 44:
            return feedback
        else:
            return None
        '''

    def start_device(self):
        self.ser = serial.Serial(port=self.port, baudrate=9600, timeout=1)
        time.sleep(2)
        if self.get_feedback() is not None:
            self.active = True
        else:
            raise ValueError("Relay Device not found")

        self.close_all_channels()

    def stop_device(self):
        try:
            self.close_all_channels()
        except Exception as error:
            print(error)
        self.active = False
        self.ser.close()

    def open_all_channels(self):
        if self.active:
            time.sleep(0.1)
            self.ser.write(str.encode("A"))
            for channel_num in self.relay_channels:
                self.channel_status[f'Channel {channel_num}'] = 1
        else:
            self.start_device()

    def close_all_channels(self):
        if self.active:
            self.ser.reset_input_buffer()
            time.sleep(0.1)
            self.ser.write(str.encode("L"))
            for channel_num in self.relay_channels:
                self.channel_status[f'Channel {channel_num}'] = 0
        else:
            self.start_device()

    def open_channel(self, channel_num):
        if self.active:
            self.ser.reset_input_buffer()
            time.sleep(0.1)
            self.ser.write(str.encode(f"O{channel_num}"))
            self.channel_status[f'Channel {channel_num}'] = 1
        else:
            self.start_device()

    def close_channel(self, channel_num):
        if self.active:
            self.ser.reset_input_buffer()
            time.sleep(0.1)
            self.ser.write(str.encode(f"C{channel_num}"))
            self.channel_status[f'Channel {channel_num}'] = 0
        else:
            self.start_device()

    def get_channel_status(self):
        if self.active:
            # just use set values to only send commands to arduino, not receive any
            return self.channel_status
            '''  # feedback from arduino serial
            feedback = self.get_feedback()
            try:
                if feedback is not None:
                    feedback = feedback.split(":")[1]
                    for ii, status in enumerate(feedback.split(",")):
                        self.channel_status[f'Channel {ii + 2}'] = int(status.strip())
                return self.channel_status
            except Exception as error:
                print('Arduino get_channel_status:', error)
                return None
            '''
        else:
            self.start_device()



if __name__ == "__main__":
    Relay = ArduinoRelay()
    Relay.start_device()
    try:
        status = Relay.get_channel_status()
        print(status)
    except Exception as error:
        print(error)

    Relay.stop_device()
