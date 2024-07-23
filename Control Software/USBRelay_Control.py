import pandas as pd
import usb.core
import usb.util
import usb.backend.libusb0
backend = usb.backend.libusb0.get_backend()

# if there are any problems, install correct driver (libusb0) for USBRelay8 via zadig: https://zadig.akeo.ie/#google_vignette

class USBRelay8:
    def __init__(self):
        self.device = None
        self.idVendor = 5824
        self.idProduct = 1503
        self.request_type_out = usb.util.CTRL_TYPE_CLASS | usb.util.CTRL_OUT
        self.request_type_in = usb.util.CTRL_TYPE_CLASS | usb.util.CTRL_IN
        self.channel_statuses = [0] * 8  # Initialize all channels to 0 (closed)

        # Initialize channel attributes
        self.channel1 = 0
        self.channel2 = 0
        self.channel3 = 0
        self.channel4 = 0
        self.channel5 = 0
        self.channel6 = 0
        self.channel7 = 0
        self.channel8 = 0

    def start_device(self):
        """
        Start the device and close all open channels to enable correct communication.
        Returns status byte array.
        """
        self.device = usb.core.find(idVendor=self.idVendor, idProduct=self.idProduct, backend=backend)
        if self.device is None:
            raise ValueError("USBRelay8: Device not found.")
        #print(self.device)
        #self.device.set_configuration()
        usb.util.dispose_resources(self.device)

        received_data = self.get_status()
        if received_data[-1] != 0:
            self.close_all_channels()
            print('USBRelay8.start_device(): There were open channels. Closing now and trying again!')
            self.start_device()
        else:
            self.set_channels()
        return received_data

    def stop_device(self):
        """
        Stop the USB Relay device by closing the connection.
        """
        if self.device is not None:
            self.close_all_channels()
            usb.util.dispose_resources(self.device)
            self.device = None

    def send_request(self, request_type, request, value, index, data_or_length):
        """
        Send a request to the device.
        """
        try:
            if request_type == 'IN':
                request_type = self.request_type_in
            elif request_type == 'OUT':
                request_type = self.request_type_out
            else:
                raise ValueError('USBRelay8.send_request(): Invalid request_type!')
            if isinstance(data_or_length, list):
                data_or_length = bytearray(data_or_length)
            received_data = self.device.ctrl_transfer(request_type, request, value, index, data_or_length)
            #print('received', received_data)
            return received_data
        except usb.core.USBError as e:
            raise Exception(f'USBRelay8.send_request(): {e}')

    def get_status(self):
        """
        Read status from the device and check status of channels. Returns status byte array.
        """
        try:
            status_byte_array = self.send_request('IN', 0x1, 0x300, 0, 0x8)
            #print('status:', status_byte_array)
            return status_byte_array
        except Exception as error:
            print(pd.Timestamp('now').strftime('%X'), f'USB Relay: {error}')

    def set_channels(self):
        """
        Update channel statuses to get current relay states. 1 (open), 0 (closed)
        """
        status_byte_array = self.get_status()
        channel_status_byte = status_byte_array[-1]
        binary_data = format(channel_status_byte, '08b')
        self.channel_statuses = [int(bit) for bit in binary_data[::-1]]

    def open_all_channels(self):
        """
        Open all channels. Returns number of bytes sent.
        """
        try:
            sent_bytes = self.send_request('OUT', 0x9, 0x300, 0, [0xFE, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00])
            self.set_channels()
            return sent_bytes
        except Exception as error:
            print(pd.Timestamp('now').strftime('%X'), f'USB Relay: {error}')

    def close_all_channels(self):
        """
        Close all channels. Returns number of bytes sent.
        """
        try:
            sent_bytes = self.send_request('OUT', 0x9, 0x300, 0, [0xFC, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00])
            self.set_channels()
            return sent_bytes
        except Exception as error:
            print(pd.Timestamp('now').strftime('%X'), f'USB Relay: {error}')

    def open_channel(self, channel_num):
        """
        Open a specified channel. Returns number of bytes sent.
        """
        try:
            channel_num = int(abs(channel_num))
            sent_bytes = self.send_request('OUT', 0x9, 0x300, 0, [0xFF, channel_num, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00])
            self.set_channels()
            return sent_bytes
        except Exception as error:
            print(pd.Timestamp('now').strftime('%X'), f'USB Relay: {error}')

    def close_channel(self, channel_num):
        """
        Close a specified channel. Returns number of bytes sent.
        """
        try:
            channel_num = int(channel_num)
            sent_bytes = self.send_request('OUT', 0x9, 0x300, 0, [0xFD, channel_num, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00])
            self.set_channels()
            return sent_bytes
        except Exception as error:
            print(pd.Timestamp('now').strftime('%X'), f'USB Relay: {error}')

    def get_channel_status(self):
        """
        Returns a dictionary with information about the status (on/off) of each channel.
        """
        channel_status = {}
        for i in range(8):
            channel_name = f'Channel {i + 1}'
            channel_status[channel_name] = self.channel_statuses[i]
        return channel_status
