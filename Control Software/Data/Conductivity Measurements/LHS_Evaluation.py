import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib as mpl



#################################################
### Dry LHS-1 - sample 0
#################################################

data_0 = pd.read_csv('Dry LHS-1 0/Data.txt', header=0, na_values=['NA', 'NaN', 'Missing'])
data_0['is_corrected'] = data_0['is_corrected'].astype('bool')
data_0 = data_0[data_0['tau_min'] >= 1.9]

dens_0_01 = 1580
dens_0_01_err = 317
dens_0_02 = 1700
dens_0_02_err = 350
dens_0_03 = 1720
dens_0_03_err = 302
dens_0_conditions = [(data_0['num'] <= 29),
                   (data_0['num'] == 31) | (data_0['num'] == 32),
                   (data_0['num'] > 32)]
dens_0_values = [dens_0_01, dens_0_02, dens_0_03]
dens_0_err_values = [dens_0_01_err, dens_0_02_err, dens_0_03_err]
data_0['density'] = np.select(dens_0_conditions, dens_0_values, default=np.nan)
data_0['density_err'] = np.select(dens_0_conditions, dens_0_err_values, default=np.nan)

data_0_uncomp = data_0[data_0['density'] == dens_0_01].copy()
data_0_comp_time = data_0[data_0['density'] == dens_0_02].copy()
data_0_comp_gas = data_0[(data_0['num'] >= 37) & (data_0['num'] < 47)].copy()
data_0_comp = data_0[(data_0['density'] == dens_0_03) & ((data_0['num'] <= 36) | (data_0['num'] >= 47))]



#################################################
### Dry LHS-1 - sample 1
#################################################

data_1 = pd.read_csv('Dry LHS-1 1/Data.txt', header=0, na_values=['NA', 'NaN', 'Missing'])
data_1['is_corrected'] = data_1['is_corrected'].astype('bool')
data_1 = data_1[data_1['tau_min'] >= 1.9]

dens_1_01 = 1600
dens_1_01_err = 120
dens_1_02 = 2160
dens_1_02_err = 77
dens_1_03 = 2220.01  # assumed to be same as 02, THS could not be smoothly inserted
dens_1_03_err = 77.001
dens_1_conditions = [(data_1['num'] <= 113 ), ((data_1['num'] >= 114) & (data_1['num'] <= 124)), (data_1['num'] >= 125)]   # add second density condition if measured!!!!!!!!!!!!!!!
dens_1_values = [dens_1_01, dens_1_02, dens_1_03]
dens_1_err_values = [dens_1_01_err, dens_1_02_err, dens_1_03_err]
data_1['density'] = np.select(dens_1_conditions, dens_1_values, default=np.nan)
data_1['density_err'] = np.select(dens_1_conditions, dens_1_err_values, default=np.nan)

data_1_uncomp = data_1[data_1['density'] == dens_1_01].copy()
data_1_comp = data_1[(data_1['density'] == dens_1_02)].copy()
data_1_comp_new = data_1[(data_1['density'] == dens_1_03)].copy()

#################################################
### Dry TUBS - sample 0
#################################################

data_TUBS_0 = pd.read_csv('Dry TUBS 0/Data.txt', header=0, na_values=['NA', 'NaN', 'Missing'])
data_TUBS_0['is_corrected'] = data_TUBS_0['is_corrected'].astype('bool')
data_TUBS_0 = data_TUBS_0[data_TUBS_0['tau_min'] >= 1.9]

dens_TUBS_0_01 = 1380
dens_TUBS_0_01_err = 82
dens_TUBS_0_02 = 1380.001
dens_TUBS_0_02_err = 82.001
dens_TUBS_0_03 = -3
dens_TUBS_0_03_err = 1
dens_TUBS_0_conditions = [(data_TUBS_0['num'] <= 1), ((data_TUBS_0['num'] >= 2) & (data_TUBS_0['num'] <= 100)), (data_TUBS_0['num'] >= 500)]
dens_TUBS_0_values = [dens_TUBS_0_01, dens_TUBS_0_02, dens_TUBS_0_03]
dens_TUBS_0_err_values = [dens_TUBS_0_01_err, dens_TUBS_0_02_err, dens_TUBS_0_03_err]
data_TUBS_0['density'] = np.select(dens_TUBS_0_conditions, dens_TUBS_0_values, default=np.nan)
data_TUBS_0['density_err'] = np.select(dens_TUBS_0_conditions, dens_TUBS_0_err_values, default=np.nan)

data_TUBS_0_p = data_TUBS_0[data_TUBS_0['density'] == dens_TUBS_0_01].copy()
data_TUBS_0_uncomp = data_TUBS_0[data_TUBS_0['density'] == dens_TUBS_0_02].copy()


#################################################
### Icy LHS-1 - sample 0
#################################################

data_icy_0 = pd.read_csv('Icy LHS-1 0/Data.txt', header=0, na_values=['NA', 'NaN', 'Missing'])
data_icy_0['is_corrected'] = data_icy_0['is_corrected'].astype('bool')
data_icy_0 = data_icy_0[data_icy_0['tau_min'] >= 1.9]

dens_icy_0_01 = 1520
dens_icy_0_01_err = 113
dens_icy_0_02 = 1520.002
dens_icy_0_02_err = 113
dens_icy_0_03 = 1520.003
dens_icy_0_03_err = 113.001
dens_icy_0_conditions = [((data_icy_0['num'] > 0) & (data_icy_0['num'] < 12)), ((data_icy_0['num'] >= 12) & (data_icy_0['num'] < 30)), (data_icy_0['num'] >= 30)]
dens_icy_0_values = [dens_icy_0_01, dens_icy_0_02, dens_icy_0_03]
dens_icy_0_err_values = [dens_icy_0_01_err, dens_icy_0_02_err, dens_icy_0_03_err]

data_icy_0['density'] = np.select(dens_icy_0_conditions, dens_icy_0_values, default=np.nan)
data_icy_0['density_err'] = np.select(dens_icy_0_conditions, dens_icy_0_err_values, default=np.nan)

data_icy_0_uncomp = data_icy_0[data_icy_0['density'] == dens_icy_0_01].copy()
data_icy_0_uncomp_dried = data_icy_0[data_icy_0['density'] == dens_icy_0_02].copy()
data_icy_0_uncomp_pressure = data_icy_0[data_icy_0['density'] == dens_icy_0_03].copy()

#################################################
### Icy LHS-1 - sample 1
#################################################

data_icy_1 = pd.read_csv('Icy LHS-1 1/Data.txt', header=0, na_values=['NA', 'NaN', 'Missing'])
data_icy_1['is_corrected'] = data_icy_1['is_corrected'].astype('bool')
data_icy_1 = data_icy_1[data_icy_1['tau_min'] >= 1.9]

dens_icy_1_01 = 1390
dens_icy_1_01_err = 119
dens_icy_1_02 = 1390.001  # same as 01, just cooldowned again, weight loss not accounted for
dens_icy_1_02_err = 119.001
dens_icy_1_03 = -3
dens_icy_1_03_err = 0
dens_icy_1_conditions = [((data_icy_1['num'] > 0) & (data_icy_1['num'] < 119)), (data_icy_1['num'] >= 119), (data_icy_1['num'] >= 5000)]
dens_icy_1_values = [dens_icy_1_01, dens_icy_1_02, dens_icy_1_03]
dens_icy_1_err_values = [dens_icy_1_01_err, dens_icy_1_02_err, dens_icy_1_03_err]

data_icy_1['density'] = np.select(dens_icy_1_conditions, dens_icy_1_values, default=np.nan)
data_icy_1['density_err'] = np.select(dens_icy_1_conditions, dens_icy_1_err_values, default=np.nan)

data_icy_1_uncomp = data_icy_1[data_icy_1['density'] == dens_icy_1_01].copy()
data_icy_1_uncomp_cooldown = data_icy_1[data_icy_1['density'] == dens_icy_1_02].copy()


#################################################
### Icy LHS-1 - sample 1
#################################################

data_icy_2 = pd.read_csv('Icy LHS-1 2/Data.txt', header=0, na_values=['NA', 'NaN', 'Missing'])
data_icy_2['is_corrected'] = data_icy_2['is_corrected'].astype('bool')
data_icy_2 = data_icy_2[data_icy_2['tau_min'] >= 1.9]

dens_icy_2_01 = 1150
dens_icy_2_01_err = 87
dens_icy_2_02 = -2
dens_icy_2_02_err = 0
dens_icy_2_03 = -3
dens_icy_2_03_err = 0
dens_icy_2_conditions = [((data_icy_2['num'] > 0) & (data_icy_2['num'] < 299)), (data_icy_2['num'] >= 500), (data_icy_2['num'] >= 5000)]
dens_icy_2_values = [dens_icy_2_01, dens_icy_2_02, dens_icy_2_03]
dens_icy_2_err_values = [dens_icy_2_01_err, dens_icy_2_02_err, dens_icy_2_03_err]

data_icy_2['density'] = np.select(dens_icy_2_conditions, dens_icy_2_values, default=np.nan)
data_icy_2['density_err'] = np.select(dens_icy_2_conditions, dens_icy_2_err_values, default=np.nan)

data_icy_2_uncomp = data_icy_2[data_icy_2['density'] == dens_icy_2_01].copy()

#################################################
### Ice Particles - sample 0
#################################################

data_ice_0 = pd.read_csv('Ice Particles 0/Data.txt', header=0, na_values=['NA', 'NaN', 'Missing'])
data_ice_0['is_corrected'] = data_ice_0['is_corrected'].astype('bool')
data_ice_0 = data_ice_0[data_ice_0['tau_min'] >= 1.9]

dens_ice_0_01 = 290
dens_ice_0_01_err = 38
dens_ice_0_02 = -2
dens_ice_0_02_err = 0
dens_ice_0_03 = -3
dens_ice_0_03_err = 0
dens_ice_0_conditions = [((data_ice_0['num'] > 0) & (data_ice_0['num'] < 119)), (data_ice_0['num'] >= 119), (data_ice_0['num'] >= 5000)]
dens_ice_0_values = [dens_ice_0_01, dens_ice_0_02, dens_ice_0_03]
dens_ice_0_err_values = [dens_ice_0_01_err, dens_ice_0_02_err, dens_ice_0_03_err]

data_ice_0['density'] = np.select(dens_ice_0_conditions, dens_ice_0_values, default=np.nan)
data_ice_0['density_err'] = np.select(dens_ice_0_conditions, dens_ice_0_err_values, default=np.nan)

data_ice_0_uncomp = data_ice_0[data_ice_0['density'] == dens_ice_0_01].copy()

#################################################
### Mud Pie - sample 0
#################################################

data_mud_0 = pd.read_csv('Mud Pie 0/Data.txt', header=0, na_values=['NA', 'NaN', 'Missing'])
data_mud_0['is_corrected'] = data_mud_0['is_corrected'].astype('bool')
data_mud_0 = data_mud_0[data_mud_0['tau_min'] >= 1.9]

dens_mud_0_01 = 1080
dens_mud_0_01_err = 96
dens_mud_0_02 = -2
dens_mud_0_02_err = 0
dens_mud_0_03 = -3
dens_mud_0_03_err = 0
dens_mud_0_conditions = [((data_mud_0['num'] > 0) & (data_mud_0['num'] < 119)), (data_mud_0['num'] >= 119), (data_mud_0['num'] >= 5000)]
dens_mud_0_values = [dens_mud_0_01, dens_mud_0_02, dens_mud_0_03]
dens_mud_0_err_values = [dens_mud_0_01_err, dens_mud_0_02_err, dens_mud_0_03_err]

data_mud_0['density'] = np.select(dens_mud_0_conditions, dens_mud_0_values, default=np.nan)
data_mud_0['density_err'] = np.select(dens_mud_0_conditions, dens_mud_0_err_values, default=np.nan)

data_mud_0_uncomp = data_mud_0[data_mud_0['density'] == dens_mud_0_01].copy()


#################################################
### Plot Data
#################################################
data_list = [data_0_uncomp, data_0_comp_time, data_0_comp, data_0_comp_gas,
             data_1_uncomp, data_1_comp, data_1_comp_new,
             data_icy_0_uncomp, data_icy_0_uncomp_dried, data_icy_0_uncomp_pressure,
             data_icy_1_uncomp, data_icy_1_uncomp_cooldown,
             data_TUBS_0_uncomp,
             data_ice_0_uncomp,
             data_mud_0_uncomp,
             data_icy_2_uncomp]
dens_list = [dens_0_01, dens_0_02, dens_0_03, dens_0_03,
             dens_1_01, dens_1_02, dens_1_03,
             dens_icy_0_01, dens_icy_0_02, dens_icy_0_03,
             dens_icy_1_01, data_icy_1_uncomp_cooldown,
             dens_TUBS_0_02,
             dens_ice_0_01,
             dens_mud_0_01,
             dens_icy_2_01]

data_colors = ['royalblue', 'navy', 'mediumblue', 'slateblue',
               'limegreen', 'mediumseagreen', 'darkgreen',
               'tab:red', 'darkcyan', 'mediumturquoise',  # deepskyblue
               'blue', 'mediumaquamarine',  # mediumaquamarine
               'tab:red',
               'tab:cyan',
               'tab:olive',
               'tab:purple']
data_markers = ['o', 's', '8', 'D',
                'v', '<', '>',
                'p', 'P', 'X',
                'd', 'd',
                '*',
                's',
                'D',
                'o']
data_labels = ['LHS-1 1580 kg m$^{-3}$, $\\phi=0.49(10)$', 'LHS-1 1700 kg m$^{-3}$, $\\phi=0.52(11)$', 'LHS-1 1720 kg m$^{-3}$, $\\phi=0.53(9)$', 'LHS-1 1720 kg m$^{-3}$, $\\phi=0.53(9)$, gas',
               'LHS-1 1600 kg m$^{-3}$, $\\phi=0.49(4)$', 'LHS-1 2160 kg m$^{-3}$, $\\phi=0.67(3)$', 'LHS-1 ~2160 kg m$^{-3}$, $\\phi=0.67(?)$',
               'Icy LHS-1 1520 kg m$^{-3}$, $\\phi=0.48(4)$, 2.24(31) wt. %', 'Dried LHS-1 1450 kg m$^{-3}$, $\\phi=0.45(3)$', 'Dry LHS-1 1450 kg m$^{-3}$, $\\phi=0.45(3)$ 1 atm',
               'Icy LHS-1 1390 kg m$^{-3}$, $\\phi=0.44(4)$, 2.94(11) wt. %', 'Icy LHS-1 1450 kg m$^{-3}$, $\\phi=0.45(1)$, 1.56(10) wt. % (cooldown)',
               'TUBS 1380 kg m$^{-3}$, $\\phi=0.43(3)$',
               'Desiccated Ice 290 kg m$^{-3}$, $\\phi=0.32(6)$',
               'Mud Pie LHS-1 1080 kg m$^{-3}$, $\\phi=0.34(3)$, 2.9(1) wt. %',
               'Icy LHS-1 1150 kg m$^{-3}$, $\\phi=0.38(3)$, 7.71(8) wt. %']
data_fit_labels = [f'Fit {label}:' for label in data_labels]



def plot_stationary_nonstationary(ax, data, color, marker, label, ms=8, elinewidth=1, capsize=5):
    # replace negative error bars with ones that end at zero
    lower_error_bound = data['thermal_cond'] - data['thermal_cond_err']
    lower_error_bound[lower_error_bound < 0] = 0
    data = data.assign(thermal_cond_err=data['thermal_cond'] - lower_error_bound)
    # plot data
    ax.errorbar(x=data['temp'], y=data['thermal_cond'],
                xerr=data['temp_err'], yerr=data['thermal_cond_err'],
                marker=marker, markerfacecolor=color, markeredgecolor=color, markersize=ms, linewidth=0, ecolor=color,
                elinewidth=elinewidth, capsize=capsize, label=label)
    '''
    ax.errorbar(x=data[~data['is_corrected']]['temp'], y=data[~data['is_corrected']]['thermal_cond'],
                xerr=data[~data['is_corrected']]['temp_err'], yerr=data[~data['is_corrected']]['thermal_cond_err'],
                marker=marker, markerfacecolor=color, markeredgecolor=color, markersize=ms, linewidth=0, ecolor=color,
                elinewidth=elinewidth, capsize=capsize, label=label)
    if data[data['is_corrected']].shape[0] != 0:
        ax.errorbar(x=data[data['is_corrected']]['temp'], y=data[data['is_corrected']]['thermal_cond'],
                    xerr=data[data['is_corrected']]['temp_err'], yerr=data[data['is_corrected']]['thermal_cond_err'],
                    marker=marker, markerfacecolor='none', markeredgecolor=color, markersize=ms, linewidth=0, ecolor=color,
                    elinewidth=elinewidth, capsize=capsize)  #, label=f'{label} corrected')
    '''

if __name__ == '__main__':

    fig_dry = plt.figure(figsize=(14, 8), dpi=100)
    ax_dry = fig_dry.subplots()
    ax_dry.grid(linestyle='dashed', alpha=0.5)
    ax_dry.set_xlabel('Temperature (K)')
    ax_dry.set_ylabel('Thermal Conductivity (W m$^{-1}$K$^{-1}$)')
    if False:  # plot log
        ax_dry.set_yscale('log')

    for ii, data in enumerate(data_list):
        if ii not in [0, 1, 2, 4, 5, 8, 12]:  # 6 wierd measurement
            continue
        plot_stationary_nonstationary(ax_dry, data, color=data_colors[ii], marker=data_markers[ii], label=data_labels[ii])

    handles, labels = ax_dry.get_legend_handles_labels()
    handles = [h[0] for h in handles]
    ax_dry.legend(handles, labels, numpoints=1, fontsize=12)

    fig_dry.tight_layout()




    fig_icy = plt.figure(figsize=(14, 8), dpi=100)
    ax_icy = fig_icy.subplots()

    ax_icy.set_xlabel('Temperature (K)')
    ax_icy.set_ylabel('Thermal Conductivity (W m$^{-1}$K$^{-1}$)')
    if False:  # plot log
        ax_icy.set_yscale('log')
        #ax_icy.set_ylim(1E-3, 2E-2)
        plt.tick_params(axis='y', which='minor')
        def minor_formatter(x, pos):
            coeff = x / (10 ** np.floor(np.log10(abs(x))))
            return f"${coeff:.0f} \cdot 10^{{{int(np.floor(np.log10(abs(x))))}}}$"
        ax_icy.yaxis.set_minor_formatter(mpl.ticker.FuncFormatter(minor_formatter))

    for ii, data in enumerate(data_list):
        if ii == 11:
            #print('icy 1 cooldown not shown (11)')
            pass
        if ii not in [7, 8, 10, 11, 13, 14, 15]:
            continue
        plot_stationary_nonstationary(ax_icy, data, color=data_colors[ii], marker=data_markers[ii], label=data_labels[ii])

    handles, labels = ax_icy.get_legend_handles_labels()
    handles = [h[0] for h in handles]
    ax_icy.legend(handles, labels, numpoints=1, fontsize=12)
    ax_icy.grid(linestyle='dashed', alpha=0.5, which='both')
    fig_icy.tight_layout()




    fig_p = plt.figure(figsize=(14, 8), dpi=100)
    ax_p = fig_p.subplots()

    ax_p.set_xlabel('Temperature (K)')
    ax_p.set_ylabel('Thermal Conductivity (W m$^{-1}$K$^{-1}$)')
    if True:  # plot log
        ax_p.set_yscale('log')
        #ax_p.set_ylim(1E-3, 2E-2)
        plt.tick_params(axis='y', which='minor')
        def minor_formatter(x, pos):
            coeff = x / (10 ** np.floor(np.log10(abs(x))))
            return f"${coeff:.0f} \cdot 10^{{{int(np.floor(np.log10(abs(x))))}}}$"
        ax_p.yaxis.set_minor_formatter(mpl.ticker.FuncFormatter(minor_formatter))

    for ii, data in enumerate(data_list):
        if ii not in [0, 3, 9]:
            continue
        plot_stationary_nonstationary(ax_p, data, color=data_colors[ii], marker=data_markers[ii], label=data_labels[ii])


    handles, labels = ax_p.get_legend_handles_labels()
    handles = [h[0] for h in handles]
    ax_p.legend(handles, labels, numpoints=1, fontsize=12)
    ax_p.grid(linestyle='dashed', alpha=0.5, which='both')
    fig_p.tight_layout()

    plt.show()

    fig_dry.savefig('LHS_evaluation.png', dpi=720)
    fig_icy.savefig('Icy_LHS_evaluation.png', dpi=720)











'''
data_list = [[326.007, 1.222, 0.0033063, 0.0000784],  # 001 - first run
             [174.908, 0.666, 0.0017967, 0.0000405],  # 002
             [175.478, 0.649, 0.0018010, 0.0000396],  # 003
             [203.490, 0.616, 0.0019999, 0.0000440],  # 004
             [203.442, 0.579, 0.0020877, 0.0000438],  # 005
             [219.417, 0.358, 0.0018925, 0.0000442],  # 006
             [221.085, 0.490, 0.0020475, 0.0000505],  # 007
             [243.386, 0.299, 0.0021076, 0.0000585],  # 008
             [244.162, 0.448, 0.0022854, 0.0000558],  # 009
             [244.291, 0.214, 0.0022072, 0.0000601],  # 010
             [257.920, 0.334, 0.0022802, 0.0000618],  # 011
             [258.496, 0.367, 0.0023790, 0.0000623],  # 012
             [258.980, 0.380, 0.0023944, 0.0000622],  # 013
             [278.525, 0.228, 0.0023714, 0.0000733],  # 014
             [279.668, 0.141, 0.0024879, 0.0000850],  # 015
             [279.855, 0.388, 0.0025620, 0.0000664],  # 016
             [297.529, 0.312, 0.0027532, 0.0000767],  # 017
             [297.762, 0.325, 0.0028232, 0.0000763],  # 018
             [317.056, 0.341, 0.0030589, 0.0000803],  # 019
             [316.876, 0.290, 0.0030816, 0.0000847],  # 020
             [336.503, 0.401, 0.0033472, 0.0000842],  # 021
             [336.290, 0.291, 0.0031260, 0.0000903],  # 022
             [336.656, 0.371, 0.0032304, 0.0000842],  # 023
             [356.330, 0.381, 0.0035334, 0.0000907],  # 024
             [356.418, 0.441, 0.0035606, 0.0000863],  # 025
             [377.929, 0.372, 0.0040578, 0.0001016],  # 026
             [377.687, 0.508, 0.0040224, 0.0000903],  # 027
             [446.096, 0.411, 0.0053256, 0.0001276],  # 028
             [446.167, 0.366, 0.0052673, 0.0001331],  # 029
             [406.227, 0.398, 0.0045217, 0.0001095],  # 030 not stationary, corrected with polynom fit
             [305.353, 0.241, 0.0032700, 0.0000941],  # 031
             [304.417, 0.381, 0.0032266, 0.0000819],  # 032 - last value in first run
             [303.243, 0.396, 0.0039516, 0.0000930],  # 033 - first value with compacted sample
             [303.219, 0.446, 0.0039444, 0.0000873],  # 034
             [314.932, 0.359, 0.0042447, 0.0001032],  # 035
             [315.203, 0.310, 0.0043727, 0.0001114],  # 036
             [334.882, 0.247, 0.0055836, 0.0001539],  # 037 - first with pump shut off
             [334.801, 0.289, 0.0057463, 0.0001483],  # 038
             [354.602, 0.259, 0.0061920, 0.0001659],  # 039
             [354.619, 0.283, 0.0064130, 0.0001607],  # 040
             [374.555, 0.311, 0.0071464, 0.0001778],  # 041
             [374.583, 0.377, 0.0072796, 0.0001744],  # 042
             [393.903, 0.375, 0.0077797, 0.0001605],  # 043
             [394.008, 0.345, 0.0080133, 0.0001725],  # 044
             [296.861, 0.291, 0.0072453, 0.0001571],  # 045
             [296.805, 0.243, 0.0074266, 0.0001790],  # 046 - last with pump shut down
             [299.006, 0.337, 0.0040830, 0.0000949],  # 047
             #[299.467, 1.158, 0.0033797, 0.0002029],  # 048 - not stationary during measurement
             [332.963, 0.417, 0.0044748, 0.0000988],  # 049
             [332.660, 0.418, 0.0045930, 0.0000995],  # 050
             [367.669, 0.364, 0.0049945, 0.0001160],  # 051
             [365.679, 0.367, 0.0050391, 0.0001163],  # 052
             [398.556, 0.351, 0.0053728, 0.0001314],  # 053
             [398.596, 0.410, 0.0055491, 0.0001226],  # 054
             [398.487, 0.376, 0.0054368, 0.0001271],  # 055
             [385.657, 0.375, 0.0053401, 0.0001200],  # 056 not stationary, corrected
             [370.530, 0.407, 0.0053648, 0.0001144],  # 057 not stationary, corrected
             [349.453, 0.360, 0.0047752, 0.0001132],  # 058 not stationary, corrected
             [331.635, 0.419, 0.0048471, 0.0000913],  # 059 not stationary, corrected
             ]
data_list = pd.DataFrame(data_list, columns=['temp', 'temp_err', 'thermal_cond', 'thermal_cond_err'])
'''