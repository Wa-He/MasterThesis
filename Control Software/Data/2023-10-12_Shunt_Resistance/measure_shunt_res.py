from SDM_Control import SDM3065X
import pandas as pd
import matplotlib.pyplot as plt

measure = False
if measure:
    SDM = SDM3065X()

    SDM.start_device()
    try:
        SDM.start_scanner_card()

        SDM.select_scan_function(scan_function='SCAN')  # measure one channel at a time, then step to next one
        SDM.set_scan_delay(0.01)  # set delay between scans in s
        SDM.set_scan_cycle_count_auto(status='ON')  # scan channels circularly until scan is ended
        SDM.set_active_channels(lower_channel_limit=9, higher_channel_limit=9)  # channel 13 for current

        SDM.configure_measurement(channel=SDM.chan_ths_shunt_volt, mode='2W', range_='200OHM', speed='SLOW')

        SDM.set_autozero(mode='RES', state='ON')


        SDM.start_scan()

        data = []
        starting_time = pd.Timestamp.now()
        latest_time = starting_time
        with open(f"{starting_time.strftime('%Y-%m-%D-%H_%M-%S')}_Shunt-Res.txt", 'w') as f:
            f.write('time, shunt_resistance\n')
            print('Now starting measurement!')
            while pd.Timestamp.now() < starting_time + pd.Timedelta(30, 'm'):
                if pd.Timestamp.now() - latest_time < pd.Timedelta(0.7, 's'):
                    continue
                try:
                    ths_shunt_voltage = SDM.read_data(channel=SDM.chan_ths_shunt_volt)
                    current_time = pd.Timestamp.now()
                    value = ths_shunt_voltage
                    try:
                        value = float(value.split()[0])
                    except:
                        value = np.nan
                    finally:
                        latest_time = pd.Timestamp.now()
                    print(current_time, value)
                    f.write(f'{current_time}, {value}\n')
                except Exception as e:
                    print(e)
                    break
    except Exception as error:
        print(error)
        SDM.stop_device()


if not measure:
    data = pd.read_csv("2023-10-12_Shunt-Res.txt", header=0)
    print(data.columns)
    data['time'] = pd.to_datetime(data['time'])
    r_shunt = data['shunt_resistance'].mean()
    r_shunt_dev = data['shunt_resistance'].std()
    print(r_shunt, r_shunt_dev)


    fig = plt.figure()
    ax = fig.subplots()

    ax.plot(data['time'], data['shunt_resistance'])
    plt.show()