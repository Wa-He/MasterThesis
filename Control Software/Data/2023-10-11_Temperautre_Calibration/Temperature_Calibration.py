import pandas as pd
import numpy as np
import scipy as sc
import matplotlib.pyplot as plt

def temp_from_pt1000(R0=1000):
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
get_pt1000_sample_holder_temp = temp_from_pt1000(R0=1000.46)

class ths_fit():
    def __init__(self):
        self.R0 = 6.043 # 6.419  # 9.3792  # temp(res) fit parameter as calibrated in ice water, std 0.0044 OHM  # initially 6.419 by DLR/Moritz?
        self.A = 0.004308  # temp(res) fit parameter, as calibrated by DLR
        self.B = -4.91 * 10 ** -7  # temp(res) fit parameter, as calibrated by DLR
        self.C = 1.41 * 10 ** -12  # temp(res) fit parameter, as calibrated by DLR
        temp = np.arange(-3000, 1000)
        res = self.R0 * self.C * (temp - 100) * temp ** 3 + self.R0 * self.B * temp ** 2 + self.R0 * self.A * temp + self.R0
        self.temperature_fit_func = sc.interpolate.interp1d(x=res, y=temp, fill_value=np.nan, bounds_error=False)

        self.shunt_resistance = 47.1291

    def temp_from_res(self, res):
        return self.temperature_fit_func(res)

    def get_res_with_shunt(self, shunt_volt, ths_volt):
        curr = shunt_volt / self.shunt_resistance
        return ths_volt / curr

    def get_res(self, ths_volt, ths_curr):
        return ths_volt / ths_curr

ths_class = ths_fit()


path_ths = 'run1/THS_2023_10_11_15_09_10.txt'
path_tvac = 'run1/TVAC_Control_2023_10_11_15_09_12.txt'
path_sdm = 'run1/SDM_Feedback_2023-10-11_15_09_44.txt'
start_time = pd.Timestamp('2023-10-11 15:40:00')
end_time = pd.Timestamp('2023-10-11 15:51:00')


path_ths_2 = 'run2/THS_2023_10_11_15_57_03.txt'
path_tvac_2 = 'run2/TVAC_Control_2023_10_11_15_57_04.txt'
path_sdm_2 = 'run2/SDM_Feedback_2023-10-11_15_57_05.txt'
start_time_2 = pd.Timestamp('2023-10-11 16:00:00')
end_time_2 = pd.Timestamp('2023-10-11 16:40:00')

path_ths_3 = 'run3/2023-10-13-12-57-26_THS.txt'
path_tvac_3 = 'run3/2023-10-13-12-57-27_TVAC_Control.txt'
path_sdm_3 = 'run3/SDM_Feedback_2023-10-13_15_02_02.txt'
start_time_3 = pd.Timestamp('2023-10-13 13:00:00')
end_time_3 = pd.Timestamp('2023-10-13 15:00:00')

run_1 = [path_ths, path_tvac, path_sdm, start_time, end_time, 1]
run_2 = [path_ths_2, path_tvac_2, path_sdm_2, start_time_2, end_time_2, 2]
run_3 = [path_ths_3, path_tvac_3, path_sdm_3, start_time_3, end_time_3, 3]

for path_ths, path_tvac, path_sdm, start_time, end_time, fig_num in [run_3]:

    ths_data = pd.read_csv(path_ths, header=0)
    tvac_data = pd.read_csv(path_tvac, header=0)
    sdm_data = pd.read_csv(path_sdm, sep=',', names=['time', 'sample_holder_res', 'exhaust_res', 'ths_voltage', 'ths_current', 'shunt_voltage', 'none'])

    ths_data['time'] = pd.to_datetime(ths_data['time'])
    tvac_data['time'] = pd.to_datetime(tvac_data['time'])
    sdm_data['time'] = pd.to_datetime(sdm_data['time'])

    ths_data = ths_data[(ths_data['time']>start_time)&(ths_data['time']<end_time)]
    tvac_data = tvac_data[(tvac_data['time']>start_time)&(tvac_data['time']<end_time)]
    sdm_data = sdm_data[(sdm_data['time']>start_time)&(sdm_data['time']<end_time)]

    ths_data['resistance'] = ths_data['voltage'] / ths_data['current']

    sdm_data = sdm_data.replace('OHM', '')
    sdm_data = sdm_data.replace('VDC', '')
    sdm_data = sdm_data.replace('ADC', '')
    sdm_data = sdm_data.where(sdm_data['sample_holder_res']!=0)


    sample_holder_res = sdm_data['sample_holder_res'].mean()
    sample_holder_res_dev = sdm_data['sample_holder_res'].std()
    print('sample holder res:', sample_holder_res, sample_holder_res_dev)

    #sample_holder_temp = tvac_data['sample_holder_temp'].mean()
    #sample_holder_temp_dev = tvac_data['sample_holder_temp'].std()
    #print('sample holder temp:', sample_holder_temp, sample_holder_temp_dev)

    ths_res = ths_data['resistance'].mean()
    ths_res_dev = ths_data['resistance'].std()
    print('ths resistance:', ths_res, ths_res_dev)



    fig = plt.figure(fig_num)
    ax = fig.subplots()

    ax.plot(sdm_data['time'], sdm_data['sample_holder_res'], color='red', label='sample holder OHM')
    ax.hlines(xmin=sdm_data['time'].min(), xmax=sdm_data['time'].max(), y=1000.46, color='red')
    #ax.set_ylim(1000, 1001)

    ax2 = ax.twinx()
    ax2.plot(ths_data['time'], ths_data['resistance'], color='green', label='ths res')
    #ax2.set_ylim(6.033, 6.036)

    lines1, labels1 = ax.get_legend_handles_labels()
    lines2, labels2 = ax2.get_legend_handles_labels()
    lines = lines1 + lines2
    labels = labels1 + labels2

    ax.legend(lines, labels, loc="best")

    plt.show()




    fig = plt.figure(fig_num+1)
    ax = fig.subplots()

    ax.plot(ths_data['time'], ths_class.temp_from_res(ths_data['resistance'])+273.15, color='green')
    ax.plot(sdm_data['time'], get_pt1000_sample_holder_temp(sdm_data['sample_holder_res']), color='red')

    ax.set_ylim(273, 273.30)

    plt.show()



