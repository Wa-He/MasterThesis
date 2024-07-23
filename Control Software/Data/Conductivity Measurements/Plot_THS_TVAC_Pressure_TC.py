import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import os

from LHS_Evaluation import data_list, data_colors, data_markers, data_labels, data_fit_labels


def plot_stationary_nonstationary(ax, data, color, marker, label, ms=8, elinewidth=1, capsize=5):
    ax.errorbar(x=data[~data['is_corrected']]['temp'], y=data[~data['is_corrected']]['thermal_cond'],
                xerr=data[~data['is_corrected']]['temp_err'], yerr=data[~data['is_corrected']]['thermal_cond_err'],
                marker=marker, markerfacecolor=color, markeredgecolor=color, markersize=ms, linewidth=0, ecolor=color,
                elinewidth=elinewidth, capsize=capsize, label=label)
    if data[data['is_corrected']].shape[0] != 0:
        ax.errorbar(x=data[data['is_corrected']]['temp'], y=data[data['is_corrected']]['thermal_cond'],
                    xerr=data[data['is_corrected']]['temp_err'], yerr=data[data['is_corrected']]['thermal_cond_err'],
                    marker=marker, markerfacecolor='none', markeredgecolor=color, markersize=ms, linewidth=0, ecolor=color,
                    elinewidth=elinewidth, capsize=capsize, label=f'{label} corrected')
# name - start - stop
dict_intervals = {'Dry LHS-1 0': {'start': '2023-10-24 14:30:00', 'end': '2024-01-25 09:00:00', 'idx': [0,1,2]},
                  'Dry LHS-1 1': {'start': '2024-02-01 14:30:00', 'end': '2024-03-05 09:15:00', 'idx': [4,5,6]},
                  'Dry TUBS 0': {'start': '2024-04-27 00:00:00', 'end': '2024-05-08 08:00:00', 'idx': [12]},

                  'Icy LHS-1 0': {'start': '2024-03-05 17:19:00', 'end': '2024-03-14 11:24:00', 'idx': [7, 8]}, # 'Icy LHS-1 0': {'start': '2024-03-05 17:19:00', 'end': '2024-03-22 12:30:00', 'idx': [7, 8]}, # with dried
                  'Icy LHS-1 1': {'start': '2024-04-05 18:11:38', 'end': '2024-04-23 10:30:28', 'idx': [10, 11]},
                  'Icy LHS-1 2': {'start': '2024-06-14 18:21:34', 'end': '2024-06-24 09:20:00', 'idx': [15]},
                  'Ice Particles 0': {'start': '2024-05-08 16:00:00', 'end': '2024-05-14 12:00:34', 'idx': [13]},
                  'Mud Pie 0': {'start': '2024-05-30 10:11:44', 'end': '2024-06-13 09:42:55', 'idx': [14]}
                  }


sample_name = 'Ice Particles 0'
start_time = pd.Timestamp(dict_intervals[sample_name]['start'])
end_time = pd.Timestamp(dict_intervals[sample_name]['end'])
sample_ids = dict_intervals[sample_name]['idx']

path = r'..\Archive'


plot_tc = False


data_TVAC = []
data_THS = []
data_pressure = []
for file in os.listdir(path):
    if file.endswith('TVAC_Control.txt'):
        data_TVAC.append(pd.read_csv(os.path.join(path, file), header=0))
    elif file.endswith('THS.txt'):
        data_THS.append(pd.read_csv(os.path.join(path, file), header=0))

data_TVAC = pd.concat(data_TVAC)
data_TVAC['time'] = pd.to_datetime(data_TVAC['time'])
data_TVAC.sort_values(by='time', inplace=True)
data_TVAC = data_TVAC[(data_TVAC['time'] >= start_time) & (data_TVAC['time'] <= end_time)]

data_THS = pd.concat(data_THS)
data_THS['time'] = pd.to_datetime(data_THS['time'])
data_THS.sort_values(by='time', inplace=True)
data_THS = data_THS[(data_THS['time'] >= start_time) & (data_THS['time'] <= end_time)]


path_pressure = '../Pressuredata'
for file in os.listdir(path_pressure):
    filepath = os.path.join(path_pressure, file)
    if os.path.isdir(filepath):
        continue
    data_pressure.append(pd.read_csv(os.path.join(path_pressure, file), header=0))

data_pressure = pd.concat(data_pressure)
data_pressure = data_pressure.dropna()
try:
    data_pressure['time'] = pd.to_datetime(data_pressure['time'], format='mixed')
except ValueError:
    data_pressure['time'] = pd.to_datetime(data_pressure['time'], format="%Y-%m-%d %H:%M:%S")
data_pressure.sort_values(by='time', inplace=True)
data_pressure = data_pressure[(data_pressure['time'] >= start_time) & (data_pressure['time'] <= end_time)]

print('Moving average shut off !!!!')
#data_pressure['pressure'] = data_pressure['pressure'].rolling(window=60).mean()



fig, (ax2, ax1) = plt.subplots(2, 1, figsize=(14, 8), sharex=True, gridspec_kw={'hspace': 0.05, 'height_ratios': [1, 3]})

ax1.plot(data_TVAC['time'], data_TVAC['sample_holder_temp'], label='Sample Holder', color='blue')
ax1.plot(data_THS['time'], data_THS['temperature'], label='THS', color='green')

ax1.set_ylabel('Temperature (K)')
ax1.set_xlabel('Time')
#ax1.set_ylim(100, 400)
#ax1.set_xlim(pd.Timestamp('2024-03-08 12:00:00'), pd.Timestamp('2024-03-10 12:00:00'))

locator = mdates.AutoDateLocator(minticks=3, maxticks=9)
formatter = mdates.ConciseDateFormatter(locator)
ax1.xaxis.set_major_locator(locator)
ax1.xaxis.set_major_formatter(formatter)

ax2.plot(data_pressure['time'], data_pressure['pressure'], label='TVAC Pressure', color='black')
ax2.set_yscale('log')
ax2.set_ylim(2E-6, 2E-1)
ax2.set_ylabel('TVAC Pressure (mbar)')

if plot_tc:
    ax1_tc = ax1.twinx()
    for ii, data_tc in enumerate(data_list):
        if ii not in sample_ids:
            continue
        data_tc['datetime'] = pd.to_datetime(data_tc['datetime'])
        ax1_tc.errorbar(x=data_tc['datetime'], y=data_tc['thermal_cond'], yerr=data_tc['thermal_cond_err'],
                        marker=data_markers[ii], markerfacecolor=data_colors[ii], markeredgecolor=data_colors[ii], markersize=8, linewidth=0, ecolor=data_colors[ii],
                        elinewidth=1, capsize=5, label=data_labels[ii], alpha=0.5)
    ax1_tc.set_ylabel('Thermal Conductivity (W m$^{-1}$ K$^{-1})$')

    handles, labels = ax1.get_legend_handles_labels()
    handles2, labels2 = ax1_tc.get_legend_handles_labels()
    labels += labels2
    handles += handles2
    ax1.legend(handles, labels, loc="best")
else:
    ax1.legend(loc='best')

ax1.grid(axis='both', linestyle='dashed', linewidth=0.5)
ax2.grid(axis='both', linestyle='dashed', linewidth=0.5)

sample_name_line = sample_name.replace(' ', '_')
fig.savefig(f'{sample_name}/{sample_name_line}_Temperature_Pressure_Profile.png', dpi=720, bbox_inches='tight')


plt.show()

fig.savefig(f'{sample_name}/{sample_name_line}_Temperature_Pressure_Profile_closeup.png', dpi=720, bbox_inches='tight')
