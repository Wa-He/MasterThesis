import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

# measured with old setup
fgb_old_01 = [299.827, 3.684, 0.01151, 0.00033]
fgb_old_02 = [303.577, 6.045, 0.0114, 0.00032]
# measured with new setup
fgb_001 = [302.672, 0.109, 0.0125276, 0.0002725]
fgb_002 = [326.355, 0.320, 0.0151726, 0.0003083]
fgb_003 = [325.085, 0.575, 0.0152468, 0.0003679]
fgb_004 = [323.131, 0.926, 0.0147871, 0.0003997]
fgb_005 = [273.395, 1.271, 0.0068347, 0.0006610]
fgb_006 = [271.938, 0.889, 0.0097528, 0.0003925]
fgb_007 = [271.594, 0.825, 0.0105082, 0.0003427]
# format data into list
data_old_list = pd.DataFrame([fgb_old_01, fgb_old_02], columns=['temp', 'temp_err', 'thermal_cond', 'thermal_cond_err'])
data_list = pd.DataFrame([fgb_001, fgb_002, fgb_003, fgb_004, fgb_006, fgb_007], columns=['temp', 'temp_err', 'thermal_cond', 'thermal_cond_err'])

# plot data with errors
fig = plt.figure(figsize=(14, 8), dpi=300)
ax = fig.subplots()
ax.grid(linestyle='dashed', alpha=0.5)
ax.set_xlabel('Temperature (K)')
ax.set_ylabel('Thermal Conductivity (W m$^{-1}$K$^{-1}$)')
ax.errorbar(x=data_list['temp'], y=data_list['thermal_cond'], xerr=data_list['temp_err'], yerr=data_list['thermal_cond_err'],
            fmt='ko', markersize=5, linewidth=0, ecolor='k', elinewidth=1, capsize=5, label='new setup')
ax.errorbar(x=data_old_list['temp'], y=data_old_list['thermal_cond'], xerr=data_old_list['temp_err'], yerr=data_old_list['thermal_cond_err'],
            fmt='ks', markersize=5, linewidth=0, ecolor='k', elinewidth=1, capsize=5, label='old setup')
#fig.tight_layout()
ax.legend()
plt.savefig('FGB_evaluation.png', dpi=720)


'''
import scipy as sc
class THS_mockup:
    def __init__(self):
        self.R0 = 6.0166  # temp(res) fit parameter as calibrated in ice water, std: 0.003. first cal: 6.036, std 0.007, init 6.419 by DLR/Moritz?
        self.A = 0.004308  # temp(res) fit parameter, as calibrated by DLR
        self.B = -4.91 * 10 ** -7  # temp(res) fit parameter, as calibrated by DLR
        self.C = 1.41 * 10 ** -12  # temp(res) fit parameter, as calibrated by DLR
        temp = np.arange(-273.15, 1000, 0.05)
        res = self.R0 * self.C * (
                temp - 100) * temp ** 3 + self.R0 * self.B * temp ** 2 + self.R0 * self.A * temp + self.R0
        self.temperature_fit_func = sc.interpolate.interp1d(x=res, y=temp, fill_value=np.nan, bounds_error=False)
THS = THS_mockup()

path = r'FGB Glass 008 - old mes 1\2023-07-01-10-39-36_THS.txt'
path2 = r'FGB Glass 009 - old mes 2\2023-08-07-10-15-02_THS.txt'

df = pd.read_csv(path, header=0)
try:
    df['time'] = pd.to_datetime(df['time'], format='%d_%m_%Y_%H:%M:%S.%f')
except:
    df['time'] = pd.to_datetime(df['time'])

df['current'] = df['shunt_voltage'] / 47.1291
df['temperature'] = THS.temperature_fit_func(df['voltage']/df['current']) + 273.15

df = df[df['time'] <= pd.Timestamp('2023-07-01 15:02:00')]
print(df['time'].max())
df.to_csv(path, index=False)
'''