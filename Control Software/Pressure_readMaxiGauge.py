import serial
import pandas as pd
import time


ACK = b'\x06'  # acknowledge
NAK = b'\x15'  # negative acknowledge
CR = b'\x0D'  # carriage return
LF = b'\x0A'  # line feed
ENQ = b'\x05'  # ENQUIRY - needed for data transmission

response_key = ACK+CR+LF

def start_pressure_reading(ser, filename, sensor_number):
    # establish which pressure to read
    ser.write('PR6'.encode() + CR + LF)
    response = ''
    while True:
        response += ser.read().decode('utf-8')
        if response.endswith(response_key.decode('utf-8')):
            break
    # open file
    while True:
        ser.write(ENQ)  # ask for values

        reading = ser.readline()  # read values
        if reading[-2:] == CR+LF:
            pressure = reading[:-2].decode('utf-8').split(',')[1]
            datetime = pd.Timestamp.now()
            print(datetime, pressure)
            with open(filename, 'a') as file:
                file.write(f'{datetime},{pressure}\n')

            time.sleep(10)

filepath = 'Data/Pressuredata/' + pd.Timestamp.now().strftime('%Y-%m-%d-%H-%M-%S') + '_Pressure.txt'

try:
    ser = serial.Serial('COM4', baudrate=9600)
    start_pressure_reading(ser, filepath, 6)

except Exception as error:
    print(error)
finally:
    ser.close()


