# -*- coding: utf-8 -*-
# gui elements and window
import tkinter as tk
import customtkinter as ctk
from customtkinter import CTkButton, CTkLabel, CTkEntry
from tkinter import messagebox as mb
from tkinter import filedialog
import os  # for filepath

# data plotting
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import matplotlib.dates as mdates

# calculations
import pandas as pd
from threading import Thread

# device and system control
import pyvisa
from SDM_Control import SDM3065X
# from USBRelay_Control import USBRelay8
from ArduinoRelay_Control import ArduinoRelay
from TVAC_Control import TVAC_Control
from THS_Control import THS_Control

#  gui apps
from SliderApp import IntervalSliderApp
from ListInputApp import ListInputApp

# initialize devices
rm = pyvisa.ResourceManager()
SDM = SDM3065X(rm)
USB_Relay = ArduinoRelay()  # USBRelay8()
TVAC_Control = TVAC_Control()
THS = THS_Control(rm)

last_sdm_stop_time = pd.Timestamp('now')
last_sdm_start_time = pd.Timestamp('now')
last_sdm_reset_time = pd.Timestamp('now')

# initialize values
start_time = pd.Timestamp.now()  # initialized value for sliders
new_target_temp = None
old_target_temp = None
sweep_interval = pd.Timedelta(1, 'min')
autosweep_start_time = None
autosweep_start_temp = None
previous_temp_gradient = 0
last_target_set_time = pd.Timestamp.now() - sweep_interval
waiting_for_autotuning = False
autotune_interval = pd.Timedelta(10 / THS.temp_gradient, 'h')  # autotune PID every ~10K
last_autotune_time = pd.Timestamp.now()
# initialized values for plot from file
plot_tvac_file = False
tvac_filepaths_to_plot = ()
plot_dir_tvac = False
plot_tvac_temp_toggle = 'sample_holder'
plot_tvac_sample_holder_toggle = True
plot_tvac_temp_control_toggle = True
stop_tvac_slider_update = False
plot_ths_file = False
ths_filepaths_to_plot = ()
plot_dir_ths = False
stop_ths_slider_update = False

save_ths_plot = False
save_tvac_plot = False

# positioning values
button_width = 0.07
button_set_width = 0.04
button_height = 0.075
label_height = 0.02
gap_width = 0.015
gap_height = 0.02
tvac_rely = 0.5825


root = ctk.CTk()
try:
    # initialize window properties
    root.title('TVAC THS Control')
    root.iconbitmap("THS.ico")
    root.wm_iconbitmap('THS.ico')
    root.focus_set()  # always open in foreground
    screen_width = root.winfo_screenwidth()
    screen_height = root.winfo_screenheight()
    x_position, y_position = (0, 0)
    root.geometry(f'{screen_width}x{screen_height}+{x_position}+{y_position}')
    root.resizable(width=True, height=True)
    root.attributes('-topmost', True)


    def on_closing():
        # allow closing only if everything is turned off
        if TVAC_Control.running is False and THS.running is False and SDM.active is False:
            root.destroy()
        else:
            mb.showinfo("Exit disabled",
                        "You can not exit right now, there are still active processes!",
                        icon=mb.WARNING)


    root.protocol("WM_DELETE_WINDOW", on_closing)

    # style and appearance
    ctk.set_appearance_mode("dark")
    background_color = ('#8794a3', '#424952')
    root.configure(fg_color=background_color)

    button_style = {'fg_color': '#6d7a87', 'hover_color': '#6c8094'}  # '#6c8094'}
    label_style = {}
    entry_style = {}

    ############################################# Threading Methods ####################################################
    ####################################################################################################################
    ####################################################################################################################
    def threading_start_sdm():
        global SDM
        SDM = SDM3065X(rm)
        thread_sdm_start = Thread(target=SDM.start_device,
                                  kwargs={'output': sdm_output, 'error_output': error_out})
        thread_sdm_start.start()


    def threading_stop_sdm():
        global SDM
        thread_sdm_stop = Thread(target=SDM.stop_device())
        thread_sdm_stop.start()


    ####################################################################################################################


    def threading_sdm_start_tvac_measurement():
        global SDM
        thread_sdm_start_tvac_measure = Thread(target=SDM.start_tvac_measuring,
                                               kwargs={'output': sdm_output, 'error_output': error_out})
        thread_sdm_start_tvac_measure.start()
        threading_reset_SDM_instances()


    def threading_start_tvac_control():
        global TVAC_Control, USB_Relay
        thread_tvac_start = Thread(target=TVAC_Control.start_tvac_control,
                                   kwargs={'SDM': SDM, 'USB_Relay': USB_Relay, 'output': tvac_control_output,
                                           'error_output': error_out,
                                           'input_target_temp': tvac_control_set_target_temp, 'input_PID': tvac_control_set_PID,
                                           'input_time_delta': tvac_control_set_timedelta,
                                           'input_PID_time_interval': tvac_control_set_PID_time_interval,
                                           'input_PID_min_rel_cooling_time': tvac_control_set_PID_min_rel_cooling_time,
                                           'input_PID_max_rel_cooling_time': tvac_control_set_PID_max_rel_cooling_time,
                                           'input_failsave_overflow_ratio': tvac_control_set_failsave_overflow_ratio})
        thread_tvac_start.start()


    def threading_start_cooling():
        global TVAC_Control
        thread_tvac_start_cool = Thread(target=TVAC_Control.start_cooling)
        thread_tvac_start_cool.start()


    def threading_stop_cooling():
        global TVAC_Control
        thread_tvac_stop_cool = Thread(target=TVAC_Control.stop_cooling)
        thread_tvac_stop_cool.start()


    def threading_start_heating():
        global TVAC_Control
        thread_tvac_start_heat = Thread(target=TVAC_Control.start_heating)
        thread_tvac_start_heat.start()


    def threading_stop_heating():
        global TVAC_Control
        thread_tvac_stop_heat = Thread(target=TVAC_Control.stop_heating)
        thread_tvac_stop_heat.start()


    def threading_set_target_temp():
        thread_tvac_set_targ = Thread(target=TVAC_Control.set_target_temp)
        thread_tvac_set_targ.start()


    def threading_start_PID():
        global TVAC_Control
        thread_tvac_start_PID = Thread(target=TVAC_Control.start_PID)
        thread_tvac_start_PID.start()


    def threading_stop_PID():
        global TVAC_Control
        thread_tvac_stop_PID = Thread(target=TVAC_Control.stop_PID)
        thread_tvac_stop_PID.start()


    def threading_start_autotunePID():
        global TVAC_Control
        thread_tvac_start_autoPID = Thread(target=TVAC_Control.PID_autotuning,
                                           kwargs={'PID_Entry': tvac_control_set_PID,
                                                   'target_temp_entry': tvac_control_set_target_temp})
        thread_tvac_start_autoPID.start()


    def threading_set_PID():
        global TVAC_Control
        thread_tvac_set_PID = Thread(target=TVAC_Control.set_PID)
        thread_tvac_set_PID.start()


    def threading_set_time_delta():
        global TVAC_Control
        thread_tvac_set_time_delta = Thread(target=TVAC_Control.set_timedelta)
        thread_tvac_set_time_delta.start()


    def threading_set_PID_time_interval():
        global TVAC_Control
        thread_tvac_set_PID_time_interval = Thread(target=TVAC_Control.set_PID_time_interval)
        thread_tvac_set_PID_time_interval.start()


    def threading_set_PID_min_rel_cooling_time():
        global TVAC_Control
        thread_tvac_set_PID_min_rel_cooling_time = Thread(target=TVAC_Control.set_PID_min_rel_cooling_time)
        thread_tvac_set_PID_min_rel_cooling_time.start()


    def threading_set_PID_max_rel_cooling_time():
        global TVAC_Control
        thread_tvac_set_PID_max_rel_cooling_time = Thread(target=TVAC_Control.set_PID_max_rel_cooling_time)
        thread_tvac_set_PID_max_rel_cooling_time.start()


    def threading_set_failsave_overlow_ratio():
        global TVAC_Control
        thread_tvac_set_failsave_overlow_ratio = Thread(target=TVAC_Control.set_failsave_overlow_ratio)
        thread_tvac_set_failsave_overlow_ratio.start()


    def threading_tvac_control_check():
        global TVAC_Control
        thread_tvac_check = Thread(target=TVAC_Control.check_tvac_control)
        thread_tvac_check.start()


    def threading_stop_tvac_control():
        global TVAC_Control
        thread_tvac_stop = Thread(target=TVAC_Control.stop_tvac_control)
        thread_tvac_stop.start()


    ####################################################################################################################


    def threading_start_THS():
        global THS, SDM
        thread_ths_start = Thread(target=THS.start_THS,
                                  kwargs={'SDM': SDM, 'output': ths_output, 'error_output': error_out,
                                          'input_voltage': ths_measure_voltage,
                                          'input_stationary_time': ths_stationary_time_input,
                                          'input_heating_time': ths_heating_time_input,
                                          'input_list': ths_list_input,
                                          'input_temp_gradient': ths_temp_gradient_input})
        thread_ths_start.start()


    def threading_THS_idle():
        global THS
        thread_ths_idle = Thread(target=THS.start_idle_mode)
        thread_ths_idle.start()
        ths_button_set_idle.configure(fg_color=button_style.get('fg_color'))
        ths_button_set_manual.configure(fg_color=button_style.get('fg_color'))
        ths_button_set_autocycle.configure(fg_color=button_style.get('fg_color'))
        ths_button_set_autocycle_non_stat.configure(fg_color=button_style.get('fg_color'))
        ths_button_set_autosweep.configure(fg_color=button_style.get('fg_color'))


    def threading_THS_manually():
        global THS
        thread_ths_manually = Thread(target=THS.start_manual_measurement)
        thread_ths_manually.start()
        ths_button_set_idle.configure(fg_color=button_style.get('fg_color'))
        ths_button_set_manual.configure(fg_color=button_style.get('fg_color'))
        ths_button_set_autocycle.configure(fg_color=button_style.get('fg_color'))
        ths_button_set_autocycle_non_stat.configure(fg_color=button_style.get('fg_color'))
        ths_button_set_autosweep.configure(fg_color=button_style.get('fg_color'))


    def threading_THS_autocycle():
        global THS
        thread_ths_autocycle = Thread(target=THS.start_autocycle_measurement)
        thread_ths_autocycle.start()
        ths_button_set_idle.configure(fg_color=button_style.get('fg_color'))
        ths_button_set_manual.configure(fg_color=button_style.get('fg_color'))
        ths_button_set_autocycle.configure(fg_color=button_style.get('hover_color'))
        ths_button_set_autocycle_non_stat.configure(fg_color=button_style.get('fg_color'))
        ths_button_set_autosweep.configure(fg_color=button_style.get('fg_color'))


    def threading_THS_autocycle_non_stat():
        global THS
        thread_ths_autocycle_non_stat = Thread(target=THS.start_autocycle_non_stat_measurement)
        thread_ths_autocycle_non_stat.start()
        ths_button_set_idle.configure(fg_color=button_style.get('fg_color'))
        ths_button_set_manual.configure(fg_color=button_style.get('fg_color'))
        ths_button_set_autocycle.configure(fg_color=button_style.get('fg_color'))
        ths_button_set_autocycle_non_stat.configure(fg_color=button_style.get('hover_color'))
        ths_button_set_autosweep.configure(fg_color=button_style.get('fg_color'))


    def threading_THS_autosweep():
        global THS
        thread_ths_autosweep = Thread(target=THS.start_autosweep_mode)
        thread_ths_autosweep.start()
        ths_button_set_idle.configure(fg_color=button_style.get('fg_color'))
        ths_button_set_manual.configure(fg_color=button_style.get('fg_color'))
        ths_button_set_autocycle.configure(fg_color=button_style.get('fg_color'))
        ths_button_set_autocycle_non_stat.configure(fg_color=button_style.get('fg_color'))
        ths_button_set_autosweep.configure(fg_color=button_style.get('hover_color'))



    def threading_set_ths_measure_voltage():
        global THS
        thread_ths_set_measure_voltage = Thread(target=THS.set_measure_voltage)
        thread_ths_set_measure_voltage.start()

    def threading_set_ths_stationary_time_interval():
        global THS
        thread_ths_set_stationary_time_interval = Thread(target=THS.set_stationary_time)
        thread_ths_set_stationary_time_interval.start()

    def threading_set_ths_heating_time_interval():
        global THS
        thread_ths_set_heating_time_interval = Thread(target=THS.set_heating_time)
        thread_ths_set_heating_time_interval.start()

    def threading_set_ths_temp_gradient():
        global THS
        thread_ths_set_temp_gradient = Thread(target=THS.set_temp_gradient)
        thread_ths_set_temp_gradient.start()

    def threading_stop_THS():
        global THS
        thread_ths_stop = Thread(target=THS.stop_THS)
        thread_ths_stop.start()


    def threading_reset_SDM_instances():
        global THS, SDM
        thread_ths_reset_sdm = Thread(target=THS.reset_sdm, kwargs={'SDM': SDM})
        thread_tvac_reset_sdm = Thread(target=TVAC_Control.reset_sdm, kwargs={'SDM': SDM})
        thread_ths_reset_sdm.start()
        thread_tvac_reset_sdm.start()


    ####################################################################################################################


    def clear_error():
        error_out.delete(0, tk.END)


    def threading_clear_error():
        thread_error_clear = Thread(target=clear_error)
        thread_error_clear.start()


    ####################################################### Data Plots #################################################
    ####################################################################################################################
    ####################################################################################################################


    def plot_tvac_control_data():
        global TVAC_Control, SDM, tvac_filepaths_to_plot, plot_dir_tvac, stop_tvac_slider_update, plot_tvac_temp_toggle, \
            plot_tvac_temp_control_toggle, save_tvac_plot
        if TVAC_Control.running is False and plot_tvac_file is False:
            # error_out.delete(0, tk.END)
            # error_out.insert(0, 'TVAC Control: Inactive! Plot failed.')
            return

        if plot_tvac_file:
            filepaths = list(tvac_filepaths_to_plot)
            if plot_dir_tvac:
                directory_path = os.path.dirname(filepaths[0])
                for file_name in os.listdir(directory_path):
                    file_path = os.path.join(directory_path, file_name)
                    if os.path.isfile(file_path) and file_path not in filepaths and file_path.endswith('TVAC_Control.txt'):
                        filepaths.append(file_path)
        else:
            try:
                filepaths = ["Data/" + TVAC_Control.filename + '.txt']
            except Exception as error:
                print("plot_tvac_control_data:", error)
                return
        # clear axis
        ax_tvac_1 = tvac_control_display_axis
        ax_tvac_1.clear()
        ax_tvac_2 = tvac_control_display_axis_2
        ax_tvac_2.clear()
        try:
            # read data (if needed, concat from multiple files)
            data_list = []
            for filepath in filepaths:
                if filepath.endswith('TVAC_Control.txt'):
                    try:
                        data = pd.read_csv(filepath, header=0)
                    except Exception as error:
                        continue
                    data = data.dropna(subset=['time'])
                    data['time'] = pd.to_datetime(data['time'].values)
                    data_list.append(data)
            try:
                data_tvac = pd.concat(data_list)
            except Exception as error:
                tvac_control_output.delete(0, tk.END)
                tvac_control_output.insert(0, f'TVAC Control Plot: No files selected! {error}')
                return
            data_tvac = data_tvac.sort_values(by='time')
            data_tvac = data_tvac.reset_index(drop=True)

            if data_tvac['time'].size < 2:
                # check if there are enough values to plot
                if not SDM.active_measurement:
                    pass
                    #error_out.delete(0, tk.END)
                    #error_out.insert(0, 'TVAC Control: Plotting failed. Start SDM measurement first!')
                return
            # set slider limit to first measured time
            tvac_slider.set_new_limits(start_value=data_tvac['time'].iloc[0])
            # if plotting from file, set last limit to last value
            if plot_tvac_file:
                tvac_slider.set_new_limits(end_value=data_tvac['time'].iloc[-1])
                stop_tvac_slider_update = True
            else:
                stop_tvac_slider_update = False
            # select data range based on slider input
            data_tvac = data_tvac[
                (data_tvac['time'] >= tvac_slider.current_start) & (data_tvac['time'] <= tvac_slider.current_end)]

            # plot data based on gui button press
            if plot_tvac_temp_toggle == 'sample_holder' or plot_tvac_temp_toggle == 'both':
                ax_tvac_1.plot(data_tvac['time'], data_tvac['sample_holder_temp'], label='sample_holder_temp',
                               color='blue')

            if plot_tvac_temp_toggle == 'exhaust' or plot_tvac_temp_toggle == 'both':
                ax_tvac_1.plot(data_tvac['time'], data_tvac['exhaust_temp'], label='exhaust_temp', color='orange')

            if plot_tvac_temp_control_toggle:
                ax_tvac_2.plot(data_tvac['time'], data_tvac['heating_active'], label='heating_active', color='red',
                                linestyle='--', alpha=0.5)
                ax_tvac_2.plot(data_tvac['time'], data_tvac['cooling_active'], label='cooling_active', color='blue',
                                linestyle=':', alpha=0.5)

            # set labels and ticks
            locator = mdates.AutoDateLocator(minticks=3, maxticks=9)
            formatter = mdates.ConciseDateFormatter(locator)
            ax_tvac_1.xaxis.set_major_locator(locator)
            ax_tvac_1.xaxis.set_major_formatter(formatter)
            ax_tvac_1.set_xlabel('Time')
            ax_tvac_1.set_ylabel('Temperature (K)')

            ax_tvac_2.set_ylabel('Control System Status')
            ax_tvac_2.yaxis.set_label_position('right')

            # set visibility and limits if ax2 should not be displayed (based on gui button press)
            if plot_tvac_temp_control_toggle:
                ax_tvac_2.set_visible(True)
            if not plot_tvac_temp_control_toggle:
                ax_tvac_2.set_visible(False)
            ax_tvac_1.set_xlim(data_tvac['time'].iloc[0], data_tvac['time'].iloc[-1])

            # Get the legend handles and labels from both plots
            lines1, labels1 = ax_tvac_1.get_legend_handles_labels()
            lines2, labels2 = ax_tvac_2.get_legend_handles_labels()
            # Combine the legend handles and labels
            lines = lines1 + lines2
            labels = labels1 + labels2
            # Create a combined legend
            ax_tvac_1.legend(lines, labels, loc="best")
            ax_tvac_1.grid(axis='both', linestyle='dashed', linewidth=0.5)

            # draw graph
            tvac_control_display.draw()

            if save_tvac_plot:
                path = get_folderpath('Select directory to print')
                tvac_control_display.figure.savefig(path + "/TVAC_image.png", dpi=720)
                save_tvac_plot = False

        except Exception as error:
            print(pd.Timestamp('now').strftime('%X'), 'Error updating TVAC plot:', error)

    def plot_toggle_tvac_control_exhaust_temp():
        global plot_tvac_temp_toggle
        if plot_tvac_temp_toggle == 'sample_holder':
            plot_tvac_temp_toggle = 'exhaust'
        elif plot_tvac_temp_toggle == 'exhaust':
            plot_tvac_temp_toggle = 'both'
        elif plot_tvac_temp_toggle == 'both':
            plot_tvac_temp_toggle = 'sample_holder'


    def plot_toggle_tvac_control_temp_control():
        global plot_tvac_temp_control_toggle
        if plot_tvac_temp_control_toggle:
            plot_tvac_temp_control_toggle = False
        else:
            plot_tvac_temp_control_toggle = True

    def plot_ths_data():
        global THS, SDM, plot_ths_file, ths_filepaths_to_plot, plot_dir_ths, stop_ths_slider_update, save_ths_plot
        if THS.running is False and plot_ths_file is False:
            # error_out.delete(0, tk.END)
            # error_out.insert(0, 'THS: Inactive! Plot failed.')
            return

        if plot_ths_file:
            filepaths = list(ths_filepaths_to_plot)
            if plot_dir_ths:
                directory_path = os.path.dirname(filepaths[0])
                for file_name in os.listdir(directory_path):
                    file_path = os.path.join(directory_path, file_name)
                    if os.path.isfile(file_path) and file_path not in filepaths and file_path.endswith('THS.txt'):
                        filepaths.append(file_path)
        else:
            try:
                filepaths = ["Data/" + THS.filename + '.txt']
            except Exception as error:
                print(error)
                return
        # clear axis
        ax_ths_1 = ths_display_axis
        # ax_ths_2 = ax_ths_1.twinx()
        ax_ths_1.clear()
        # ax_ths_2.clear()
        try:
            # read data (if needed, concat from multiple files)
            data_list = []
            for filepath in filepaths:
                if filepath.endswith('THS.txt'):
                    try:
                        data = pd.read_csv(filepath, header=0)
                    except Exception as error:
                        continue
                    data = data.dropna()
                    if data.shape[0] == 0:
                        continue
                    data['time'] = pd.to_datetime(data['time'].values)
                    data_list.append(data)
            try:
                data_ths = pd.concat(data_list)
            except:
                ths_output.delete(0, tk.END)
                ths_output.insert(0, 'THS Plot: No files selected!')
                return
            data_ths = data_ths.sort_values(by='time')
            data_ths = data_ths.reset_index(drop=True)
            if data_ths['time'].size < 2:  # check if there are enough values to plot
                if SDM.active_measurement == False:
                    pass
                    #error_out.delete(0, tk.END)
                    #error_out.insert(0, 'THS: Plotting failed. Start SDM measurement first!')
                return
            # set slider limit to first measured time
            ths_slider.set_new_limits(start_value=data_ths['time'].iloc[0])
            # if plotting from file, set last limit to last value
            if plot_ths_file:
                ths_slider.set_new_limits(end_value=data_ths['time'].iloc[-1])
                stop_ths_slider_update = True
            else:
                stop_ths_slider_update = False
            # select data_ths range based on slider input
            data_ths = data_ths[
                (data_ths['time'] >= ths_slider.current_start) & (data_ths['time'] <= ths_slider.current_end)]
            # plot data
            ax_ths_1.plot(data_ths['time'], data_ths['temperature'], label='THS Temperature')

            # set labels and ticks
            locator = mdates.AutoDateLocator(minticks=3, maxticks=9)
            formatter = mdates.ConciseDateFormatter(locator)
            ax_ths_1.xaxis.set_major_locator(locator)
            ax_ths_1.xaxis.set_major_formatter(formatter)
            ax_ths_1.set_xlabel('Time')
            ax_ths_1.set_ylabel('Temperature (K)')
            ax_ths_1.set_xlim(data_ths['time'].iloc[0], data_ths['time'].iloc[-1])
            # ax_ths_2.yaxis.set_label_position('right')

            # Get the legend handles and labels from both plots
            lines1, labels1 = ax_ths_1.get_legend_handles_labels()
            # lines2, labels2 = ax_ths_2.get_legend_handles_labels()

            # Combine the legend handles and labels
            lines = lines1  # + lines2
            labels = labels1  # + labels2

            # Create a combined legend
            ax_ths_1.legend(lines, labels, loc="best")
            ax_ths_1.grid(axis='both', linestyle='dashed', linewidth=0.5)
            # draw graph
            ths_display.draw()

            if save_ths_plot:
                path = get_folderpath('Select directory to print')
                ths_display.figure.savefig(path + "/THS_image.png", dpi=720)
                save_ths_plot = False

        except Exception as error:
            print(pd.Timestamp('now').strftime('%X'), 'Error updating THS plot:', error)

    def get_filepaths(title='Select File'):
        root_getpath = tk.Tk()
        # Hide the window
        root_getpath.attributes('-alpha', 0.0)
        root_getpath.attributes('-topmost', True)
        input_paths = filedialog.askopenfilenames(title=title, initialdir=os.getcwd()+"/Data", parent=root_getpath)
        # root.withdraw()
        root_getpath.destroy()
        plot_dir = mb.askyesno("Question", "Do you want to plot all files in the same directory?")
        return input_paths, plot_dir

    def get_folderpath(title='Select Directory'):
        root_getdir = tk.Tk()
        root_getdir.attributes('-alpha', 0.0)
        root_getdir.attributes('-topmost', True)
        folder_path = filedialog.askdirectory(title=title, initialdir=os.getcwd() + "/Data", parent=root_getdir)
        root_getdir.destroy()
        return folder_path

    def plot_tvac_control_from_file():
        global plot_tvac_file, tvac_filepaths_to_plot, plot_dir_tvac
        if plot_tvac_file:
            plot_tvac_file = False
            plot_dir_tvac = False
            tvac_control_button_plot.configure(fg_color=button_style.get('fg_color'))
        else:
            stop_ths_slider_update = False
            plot_tvac_file = True
            tvac_filepaths_to_plot, plot_dir_tvac = get_filepaths()
            tvac_control_button_plot.configure(fg_color=button_style.get('hover_color'))

    def plot_ths_from_file():
        global plot_ths_file, ths_filepaths_to_plot, plot_dir_ths
        if plot_ths_file:
            plot_ths_file = False
            plot_dir_ths = False
            ths_button_plot.configure(fg_color=button_style.get('fg_color'))
        else:
            stop_ths_slider_update = False
            plot_ths_file = True
            ths_filepaths_to_plot, plot_dir_ths = get_filepaths()
            ths_button_plot.configure(fg_color=button_style.get('hover_color'))

    def save_tvac_plot_to_dir():
        global save_tvac_plot
        save_tvac_plot = True

    def save_ths_plot_to_dir():
        global save_ths_plot
        save_ths_plot = True

    def calculate_thermal_cond_from_file():
        global THS
        path = get_folderpath()
        print(path)
        re_evaluate_data = mb.askyesno('Calculation Parameters',
                                       'Do you want to re-evaluate existing data?', default='no')
        re_correct_data = mb.askyesno('Calculation Parameters',
                                      'Do you want to re-correct existing data?', default='no')
        do_correction_manually = mb.askyesno('Calculation Parameters',
                                             'Do you want to do corrections manually?', default='yes')
        do_evaluation_manually = mb.askyesno('Calculation Parameters',
                                             'Do you want to do evaluations manually?', default='yes')
        try:
            THS.calculate_thermal_conductivity_from_dir([path], re_evaluate_data, re_correct_data, do_correction_manually, do_evaluation_manually)
        except Exception as error:
            error_out.delete(0, tk.END)
            error_out.insert(0, f'Failed to calculate thermal cond. from dir: {path} {error}')
            print(error)
            return
        ths_output.delete(0, tk.END)
        ths_output.insert(0, f'Calculating thermal cond. from {path}')

    ############################################## I/O with Labels #########################################################
    ########################################################################################################################
    ########################################################################################################################
    sdm_output_label = CTkLabel(root, text='SDM System Output', **label_style)
    sdm_output = CTkEntry(root, **entry_style)
    ########################################################################################################################
    tvac_control_output_label = CTkLabel(root, text='TVAC Control Output', **label_style)
    tvac_control_output = CTkEntry(root, **entry_style)
    tvac_control_set_PID_label = CTkLabel(root, text='P, I, D', **label_style)
    tvac_control_set_PID = CTkEntry(root, **entry_style)
    tvac_control_set_timedelta_label = CTkLabel(root, text='PID Interval (min)', **label_style)
    tvac_control_set_timedelta = CTkEntry(root, **entry_style)
    tvac_control_set_PID_time_interval_label = CTkLabel(root, text='PID Cycle (min)', **label_style)
    tvac_control_set_PID_time_interval = CTkEntry(root, **entry_style)
    tvac_control_set_PID_min_rel_cooling_time_label = CTkLabel(root, text='Min Rel. Cooling', **label_style)
    tvac_control_set_PID_min_rel_cooling_time = CTkEntry(root, **entry_style)
    tvac_control_set_PID_max_rel_cooling_time_label = CTkLabel(root, text='Max Rel. Cooling', **label_style)
    tvac_control_set_PID_max_rel_cooling_time = CTkEntry(root, **entry_style)
    tvac_control_set_failsave_overflow_ratio_label = CTkLabel(root, text='Exh. Tolerance', **label_style)
    tvac_control_set_failsave_overflow_ratio = CTkEntry(root, **entry_style)
    ########################################################################################################################
    tvac_control_set_target_temp_label = CTkLabel(root, text='Target Temperature', **label_style)
    tvac_control_set_target_temp = CTkEntry(root, **entry_style)
    ########################################################################################################################
    ths_output_label = CTkLabel(root, text='THS System Output', **label_style)
    ths_output = CTkEntry(root, **entry_style)
    ths_measure_voltage_label = CTkLabel(root, text='THS Voltage', **label_style)
    ths_measure_voltage = CTkEntry(root, **entry_style)
    ths_button_set_measure_voltage = CTkButton(root, text='Set', command=threading_set_ths_measure_voltage, **button_style)
    ths_list_input_label = CTkLabel(root, text='Autocycle Temperatures', **label_style)
    ths_list_input = ListInputApp(root, entry_style=entry_style, label_style=label_style, button_style=button_style)
    ths_stationary_time_input_label = CTkLabel(root, text='Stat. Time (min)', **label_style)
    ths_stationary_time_input = CTkEntry(root, **entry_style)
    ths_heating_time_input_label = CTkLabel(root, text='Heat. Time (min)', **label_style)
    ths_heating_time_input = CTkEntry(root, **entry_style)
    ths_temp_gradient_input_label = CTkLabel(root, text='T. Gradient (K/h)', **label_style)
    ths_temp_gradient_input = CTkEntry(root, **entry_style)
    ########################################################################################################################
    error_out_label = CTkLabel(root, text='Error Output', **label_style)
    error_out = CTkEntry(root, **entry_style)
    ########################################################################################################################
    ths_display = FigureCanvasTkAgg(Figure(figsize=(14, 8), dpi=75), master=root)
    ths_display_axis = ths_display.figure.add_subplot(111)
    ths_slider = IntervalSliderApp(root, width=0.42 * root.winfo_screenwidth(),
                                   height=1.5 * label_height * root.winfo_screenheight(), start_value=start_time,
                                   end_value=pd.Timestamp.now())
    ########################################################################################################################
    tvac_control_display = FigureCanvasTkAgg(Figure(figsize=(14, 8), dpi=75), master=root)
    tvac_control_display_axis = tvac_control_display.figure.add_subplot(111)
    tvac_control_display_axis_2 = tvac_control_display_axis.twinx()
    tvac_slider = IntervalSliderApp(root, width=0.42 * root.winfo_screenwidth(),
                                    height=1.5 * label_height * root.winfo_screenheight(),
                                    start_value=start_time, end_value=pd.Timestamp.now())

    ################################################ Buttons and Style #####################################################
    ########################################################################################################################
    ########################################################################################################################
    sdm_button_start = CTkButton(root, text="Start SDM", command=threading_start_sdm, **button_style)
    sdm_button_stop = CTkButton(root, text="Stop SDM", command=threading_stop_sdm, **button_style)
    sdm_button_measure = CTkButton(root, text='Start Measure', command=threading_sdm_start_tvac_measurement,
                                **button_style)
    ########################################################################################################################
    tvac_control_button_start = CTkButton(root, text="Start\nTVAC Control", command=threading_start_tvac_control,
                                       **button_style)
    tvac_control_button_start_cool = CTkButton(root, text="Start Cooling", command=threading_start_cooling, **button_style)
    tvac_control_button_stop_cool = CTkButton(root, text="Stop Cooling", command=threading_stop_cooling, **button_style)
    tvac_control_button_start_heating = CTkButton(root, text="Start Heating", command=threading_start_heating,
                                               **button_style)
    tvac_control_button_stop_heating = CTkButton(root, text="Stop Heating", command=threading_stop_heating, **button_style)
    tvac_control_button_set_target_temp = CTkButton(root, text="Set", command=threading_set_target_temp, **button_style)
    tvac_control_button_start_PID = CTkButton(root, text="Start PID", command=threading_start_PID, **button_style)
    tvac_control_button_stop_PID = CTkButton(root, text="Stop PID", command=threading_stop_PID, **button_style)
    tvac_control_button_start_autotunePID = CTkButton(root, text='Autotune PID', command=threading_start_autotunePID,
                                                   **button_style)
    tvac_control_button_set_PID = CTkButton(root, text='Set', command=threading_set_PID, **button_style)
    tvac_control_button_set_time_delta = CTkButton(root, text='Set', command=threading_set_time_delta, **button_style)
    tvac_control_button_set_PID_time_interval = CTkButton(root, text='Set', command=threading_set_PID_time_interval, **button_style)
    tvac_control_button_set_PID_min_rel_cooling_time = CTkButton(root, text='Set', command=threading_set_PID_min_rel_cooling_time, **button_style)
    tvac_control_button_set_PID_max_rel_cooling_time = CTkButton(root, text='Set', command=threading_set_PID_max_rel_cooling_time, **button_style)
    tvac_control_button_set_failsave_overlow_ratio = CTkButton(root, text='Set', command=threading_set_failsave_overlow_ratio, **button_style)
    tvac_control_button_plot = CTkButton(root, text="Plot TVAC\nfrom File", command=plot_tvac_control_from_file, **button_style)
    tvac_control_button_plot_exhaust = CTkButton(root, text='Exhaust', command=plot_toggle_tvac_control_exhaust_temp, **button_style)
    tvac_control_button_plot_exhaust.configure(fg_color='#e3e3e3', text_color='#000', hover_color='gray', corner_radius=0)
    tvac_control_button_save_plot = CTkButton(root, text='Save', command=save_tvac_plot_to_dir, **button_style)
    tvac_control_button_save_plot.configure(fg_color='#e3e3e3', text_color='#000', hover_color='gray', corner_radius=0)
    tvac_control_button_plot_temp_control = CTkButton(root, text='Control', command=plot_toggle_tvac_control_temp_control, **button_style)
    tvac_control_button_plot_temp_control.configure(fg_color='#e3e3e3', text_color='#000', hover_color='gray', corner_radius=0)
    tvac_control_button_stop = CTkButton(root, text="Stop\nTVAC Control", command=threading_stop_tvac_control,
                                      **button_style)
    ########################################################################################################################
    ths_button_start = CTkButton(root, text="Start THS", command=threading_start_THS, **button_style)
    ths_button_set_idle = CTkButton(root, text="Start\nIdle Mode", command=threading_THS_idle, **button_style)
    ths_button_set_manual = CTkButton(root, text="Start\nManually", command=threading_THS_manually, **button_style)
    ths_button_set_autocycle = CTkButton(root, text="Start\nAutocycle", command=threading_THS_autocycle, **button_style)
    ths_button_set_autocycle_non_stat = CTkButton(root, text="Start\nAutocycle\nnon stat.", command=threading_THS_autocycle_non_stat, **button_style)
    ths_button_set_autosweep = CTkButton(root, text="Start\nTemperature\nSweep", command=threading_THS_autosweep, **button_style)
    ths_button_plot = CTkButton(root, text="Plot THS\nfrom File", command=plot_ths_from_file, **button_style)
    ths_button_stop = CTkButton(root, text="Stop THS", command=threading_stop_THS, **button_style)
    ths_button_calc_thermal_cond = CTkButton(root, text="Calculate\nThermal Conductivity\nfrom File", command=calculate_thermal_cond_from_file, **button_style)
    ths_button_set_stationary_time_interval = CTkButton(root, text='Set', command=threading_set_ths_stationary_time_interval, **button_style)
    ths_button_set_heating_time_interval = CTkButton(root, text='Set', command=threading_set_ths_heating_time_interval, **button_style)
    ths_button_set_temp_gradient = CTkButton(root, text='Set', command=threading_set_ths_temp_gradient, **button_style)
    ths_button_save_plot = CTkButton(root, text='Save', command=save_ths_plot_to_dir, **button_style)
    ths_button_save_plot.configure(fg_color='#e3e3e3', text_color='#000', hover_color='gray', corner_radius=0)
    ########################################################################################################################
    clear_error_button = CTkButton(root, text='Clear', command=threading_clear_error, **button_style)
    ########################################################################################################################
    close_button = ctk.CTkButton(root, text='EXIT', command=on_closing, fg_color=('#F00','#d11a2a'), hover_color=('#F00'))

    ############################################# Positioning ##############################################################
    ########################################################################################################################
    ########################################################################################################################
    sdm_output_label.place(relx=gap_width, rely=gap_height, relwidth=3 * button_width + 2 * gap_width,
                           relheight=label_height)
    sdm_output.place(relx=gap_width, rely=gap_height + label_height, relwidth=3 * button_width + 2 * gap_width,
                     relheight=2 * label_height)
    sdm_button_start.place(relx=gap_width, rely=2 * gap_height + 3 * label_height, relwidth=button_width,
                           relheight=button_height)
    sdm_button_stop.place(relx=2 * gap_width + button_width, rely=2 * gap_height + 3 * label_height,
                          relwidth=button_width, relheight=button_height)
    sdm_button_measure.place(relx=3 * gap_width + 2 * button_width, rely=2 * gap_height + 3 * label_height,
                             relwidth=button_width, relheight=button_height)
    ########################################################################################################################
    ths_button_start.place(relx=gap_width, rely=4 * gap_height + button_height + 6 * label_height,
                           relwidth=button_width, relheight=button_height)
    ths_button_stop.place(relx=2 * gap_width + button_width, rely=4 * gap_height + button_height + 6 * label_height,
                          relwidth=button_width, relheight=button_height)
    ths_output_label.place(relx=gap_width, rely=3 * gap_height + button_height + 3 * label_height,
                           relwidth=3 * button_width + 2 * gap_width, relheight=label_height)
    ths_output.place(relx=gap_width, rely=3 * gap_height + button_height + 4 * label_height,
                     relwidth=3 * button_width + 2 * gap_width, relheight=2 * label_height)

    ths_button_set_idle.place(relx=5 * gap_width + 4 * button_width,
                                rely=1 * gap_height + label_height, relwidth=button_width,
                                relheight=button_height)
    ths_button_set_manual.place(relx=5 * gap_width + 4 * button_width,
                                rely=2 * gap_height + label_height + button_height, relwidth=button_width,
                                relheight=button_height)
    ths_button_set_autocycle.place(relx=5 * gap_width + 4 * button_width,
                                    rely=3 * gap_height + label_height + 2*button_height, relwidth=button_width,
                                    relheight=button_height)
    ths_button_set_autocycle_non_stat.place(relx=5 * gap_width + 4 * button_width,
                                            rely=4 * gap_height + label_height + 3*button_height, relwidth=button_width,
                                            relheight=button_height)
    ths_button_set_autosweep.place(relx=5 * gap_width + 4 * button_width,
                                    rely=5 * gap_height + label_height + 4*button_height, relwidth=button_width,
                                    relheight=button_height)

    ths_measure_voltage_label.place(relx=6 * gap_width + 5 * button_width + button_set_width,
                                    rely=1 * gap_height, relwidth=1.25 * button_set_width,
                                    relheight=label_height)
    ths_measure_voltage.place(relx=6 * gap_width + 5 * button_width + button_set_width,
                              rely=1 * gap_height + 1 * label_height, relwidth=1.25 * button_set_width,
                              relheight=2 * label_height)
    ths_button_set_measure_voltage.place(relx=6 * gap_width + 5 * button_width, rely=1 * gap_height + 1 * label_height,
                                         relwidth=button_set_width, relheight=2 * label_height)
    ths_heating_time_input_label.place(relx=6 * gap_width + 5 * button_width + button_set_width,
                                       rely=2 * gap_height + 3 * label_height, relwidth=1.25 * button_set_width,
                                       relheight=label_height)
    ths_heating_time_input.place(relx=6 * gap_width + 5 * button_width + button_set_width,
                                 rely=2 * gap_height + 4 * label_height, relwidth=1.25 * button_set_width,
                                 relheight=2 * label_height)
    ths_button_set_heating_time_interval.place(relx=6 * gap_width + 5 * button_width,
                                               rely=2 * gap_height + 4 * label_height, relwidth=button_set_width,
                                               relheight=2 * label_height)

    ths_stationary_time_input_label.place(relx=6 * gap_width + 5 * button_width + button_set_width,
                                          rely=3 * gap_height + 6 * label_height, relwidth=1.25 * button_set_width,
                                          relheight=label_height)
    ths_stationary_time_input.place(relx=6 * gap_width + 5 * button_width + button_set_width,
                                    rely=3 * gap_height + 7 * label_height, relwidth=1.25 * button_set_width,
                                    relheight=2 * label_height)
    ths_button_set_stationary_time_interval.place(relx=6 * gap_width + 5 * button_width,
                                                  rely=3 * gap_height + 7 * label_height, relwidth=button_set_width,
                                                  relheight=2 * label_height)

    ths_list_input_label.place(relx=6 * gap_width + 5 * button_width, rely=4 * gap_height + 9 * label_height,
                               relwidth=1.5 * button_width, relheight=label_height)
    ths_list_input.place(relx=6 * gap_width + 5 * button_width, rely=4 * gap_height + 10 * label_height,
                         relwidth=1.5 * button_width, relheight=2 * button_height)

    ths_temp_gradient_input_label.place(relx=6 * gap_width + 5 * button_width + button_set_width,
                                        rely=5 * gap_height - 2 * label_height + 5*button_height,
                                        relwidth=1.25 * button_set_width, relheight=label_height)
    ths_temp_gradient_input.place(relx=6 * gap_width + 5 * button_width + button_set_width,
                                        rely=5 * gap_height - 1 * label_height + 5*button_height,
                                        relwidth=1.25 * button_set_width, relheight=2 * label_height)
    ths_button_set_temp_gradient.place(relx=6 * gap_width + 5 * button_width,
                                        rely=5 * gap_height - 1 * label_height + 5*button_height,
                                        relwidth=button_set_width, relheight=2 * label_height)


    ths_button_plot.place(relx=3 * gap_width + 2 * button_width, rely=4 * gap_height + button_height + 6 * label_height,
                          relwidth=button_width, relheight=button_height)
    ths_button_calc_thermal_cond.place(relx=4 * gap_width + 3 * button_width,
                                       rely=4 * gap_height + button_height + 6 * label_height,
                                       relwidth=1 * button_width, relheight=button_height)
    ths_button_save_plot.place(relx=0.96, rely=0.42 - 2 * label_height, relwidth=0.025, relheight=label_height)
    ths_display.get_tk_widget().place(relx=1 - gap_width - 0.42, rely=0.02, relwidth=0.42, relheight=0.42)
    ths_slider.place(relx=1 - gap_width - 0.42, rely=0.44, relwidth=0.42, relheight=1.5 * label_height)
    ########################################################################################################################
    tvac_control_button_start.place(relx=gap_width, rely=tvac_rely + 3 * label_height + gap_height,
                                    relwidth=button_width, relheight=button_height)
    tvac_control_button_stop.place(relx=2 * gap_width + button_width, rely=tvac_rely + 3 * label_height + gap_height,
                                   relwidth=button_width, relheight=button_height)
    tvac_control_output_label.place(relx=gap_width, rely=tvac_rely, relwidth=3 * button_width + 2 * gap_width,
                                    relheight=label_height)
    tvac_control_output.place(relx=gap_width, rely=tvac_rely + label_height, relwidth=3 * button_width + 2 * gap_width,
                              relheight=2 * label_height)
    tvac_control_button_start_cool.place(relx=gap_width,
                                         rely=tvac_rely + 3 * label_height + 2 * gap_height + button_height,
                                         relwidth=button_width, relheight=button_height)
    tvac_control_button_stop_cool.place(relx=2 * gap_width + button_width,
                                        rely=tvac_rely + 3 * label_height + 2 * gap_height + button_height,
                                        relwidth=button_width, relheight=button_height)
    tvac_control_button_start_heating.place(relx=0.185,
                                            rely=tvac_rely + 3 * label_height + 2 * gap_height + button_height,
                                            relwidth=button_width, relheight=button_height)
    tvac_control_button_stop_heating.place(relx=0.27,
                                           rely=tvac_rely + 3 * label_height + 2 * gap_height + button_height,
                                           relwidth=button_width, relheight=button_height)
    tvac_control_button_start_PID.place(relx=gap_width,
                                        rely=tvac_rely + 3 * label_height + 3 * gap_height + 2 * button_height,
                                        relwidth=button_width, relheight=button_height)
    tvac_control_button_stop_PID.place(relx=2 * gap_width + button_width,
                                       rely=tvac_rely + 3 * label_height + 3 * gap_height + 2 * button_height,
                                       relwidth=button_width, relheight=button_height)
    tvac_control_button_start_autotunePID.place(relx=0.185,
                                                rely=tvac_rely + 3 * label_height + 3 * gap_height + 2 * button_height,
                                                relwidth=button_width, relheight=button_height)
    tvac_control_set_target_temp_label.place(relx=6*gap_width+5*button_width, rely=tvac_rely - 2*label_height, relwidth=button_width, relheight=label_height)
    tvac_control_set_target_temp.place(relx=6*gap_width+5*button_width, rely=tvac_rely - label_height, relwidth=button_width, relheight=2*label_height)
    tvac_control_button_set_target_temp.place(relx=6*gap_width+5*button_width-button_set_width, rely=tvac_rely - label_height, relwidth=button_set_width, relheight=2*label_height)

    tvac_control_set_PID_label.place(relx=6*gap_width+5*button_width, rely=tvac_rely + gap_height + 1*label_height, relwidth=button_width, relheight=label_height)
    tvac_control_set_PID.place(relx=6*gap_width+5*button_width, rely=tvac_rely + gap_height + 2*label_height, relwidth=button_width, relheight=2*label_height)
    tvac_control_button_set_PID.place(relx=6*gap_width+5*button_width-button_set_width, rely=tvac_rely + gap_height + 2*label_height, relwidth=button_set_width, relheight=2*label_height)
    tvac_control_set_timedelta_label.place(relx=5*gap_width+4*button_width+button_set_width, rely=tvac_rely + 2*gap_height + 4*label_height, relwidth=1.25*button_set_width, relheight=label_height)
    tvac_control_set_timedelta.place(relx=5*gap_width+4*button_width+button_set_width, rely=tvac_rely + 2*gap_height + 5*label_height, relwidth=1.25*button_set_width, relheight=2*label_height)
    tvac_control_button_set_time_delta.place(relx=5*gap_width+4*button_width, rely=tvac_rely + 2*gap_height + 5*label_height, relwidth=button_set_width, relheight=2*label_height)
    tvac_control_set_PID_time_interval_label.place(relx=6*gap_width+4*button_width+3.25*button_set_width, rely=tvac_rely + 2*gap_height + 4*label_height, relwidth=1.25*button_set_width, relheight=label_height)
    tvac_control_set_PID_time_interval.place(relx=6*gap_width+4*button_width+3.25*button_set_width, rely=tvac_rely + 2*gap_height + 5*label_height, relwidth=1.25*button_set_width, relheight=2*label_height)
    tvac_control_button_set_PID_time_interval.place(relx=6*gap_width+4*button_width+2.25*button_set_width, rely=tvac_rely + 2*gap_height + 5*label_height, relwidth=button_set_width, relheight=2*label_height)
    tvac_control_set_PID_min_rel_cooling_time_label.place(relx=5*gap_width+4*button_width+button_set_width, rely=tvac_rely + 3*gap_height + 7*label_height, relwidth=1.25*button_set_width, relheight=label_height)
    tvac_control_set_PID_min_rel_cooling_time.place(relx=5*gap_width+4*button_width+button_set_width, rely=tvac_rely + 3*gap_height + 8*label_height, relwidth=1.25*button_set_width, relheight=2*label_height)
    tvac_control_button_set_PID_min_rel_cooling_time.place(relx=5*gap_width+4*button_width, rely=tvac_rely + 3*gap_height + 8*label_height, relwidth=button_set_width, relheight=2*label_height)
    tvac_control_set_PID_max_rel_cooling_time_label.place(relx=6*gap_width+4*button_width+3.25*button_set_width, rely=tvac_rely + 3*gap_height + 7*label_height, relwidth=1.25*button_set_width, relheight=label_height)
    tvac_control_set_PID_max_rel_cooling_time.place(relx=6*gap_width+4*button_width+3.25*button_set_width, rely=tvac_rely + 3*gap_height + 8*label_height, relwidth=1.25*button_set_width, relheight=2 * label_height)
    tvac_control_button_set_PID_max_rel_cooling_time.place(relx=6*gap_width+4*button_width+2.25*button_set_width, rely=tvac_rely + 3*gap_height + 8*label_height, relwidth=button_set_width, relheight=2*label_height)
    tvac_control_set_failsave_overflow_ratio_label.place(relx=5*gap_width+4*button_width+button_set_width, rely=tvac_rely + 4*gap_height + 10*label_height, relwidth=1.25*button_set_width, relheight=label_height)
    tvac_control_set_failsave_overflow_ratio.place(relx=5*gap_width+4*button_width+button_set_width, rely=tvac_rely + 4*gap_height + 11*label_height, relwidth=1.25*button_set_width, relheight=2*label_height)
    tvac_control_button_set_failsave_overlow_ratio.place(relx=5*gap_width+4*button_width, rely=tvac_rely + 4*gap_height + 11*label_height, relwidth=button_set_width, relheight=2*label_height)

    tvac_control_button_plot.place(relx=2 * button_width + 3 * gap_width, rely=tvac_rely + 3 * label_height + gap_height, relwidth=button_width, relheight=button_height)
    tvac_control_button_save_plot.place(relx=0.96, rely=0.88 - 2 * label_height, relwidth=0.025, relheight=label_height)
    tvac_control_button_plot_exhaust.place(relx=0.96, rely=0.88, relwidth=0.025, relheight=label_height)
    tvac_control_button_plot_temp_control.place(relx=0.96, rely=0.88-label_height, relwidth=0.025, relheight=label_height)
    tvac_control_display.get_tk_widget().place(relx=1 - gap_width - 0.42, rely=0.48, relwidth=0.42, relheight=0.42)
    tvac_slider.place(relx=1 - gap_width - 0.42, rely=0.48 + 0.42, relwidth=0.42, relheight=1.5 * label_height)
    ########################################################################################################################
    error_out_label.place(relx=2 * gap_width + button_width, rely=0.48 - 2 * label_height,
                          relwidth=3 * button_width + 2 * gap_width, relheight=label_height)
    error_out.place(relx=2 * gap_width + button_width, rely=0.48 - label_height,
                    relwidth=3 * button_width + 2 * gap_width, relheight=2 * label_height)
    clear_error_button.place(relx=2 * gap_width + button_width, rely=0.48 + label_height, relwidth=button_set_width,
                             relheight=1.2 * label_height)
    ########################################################################################################################
    close_button.place(relx=gap_width, rely=0.48 - 0.5 * 1.2 * button_height, relwidth=button_width,
                       relheight=button_height)


    #################################################### Update methods ####################################################
    ########################################################################################################################
    ########################################################################################################################
    def on_slider_click(event):
        for slider in [tvac_slider, ths_slider]:
            # check if a click was made on the slider or not
            x_root, y_root = event.x_root, event.y_root
            if (slider.winfo_rootx() <= x_root <= slider.winfo_rootx() + slider.width
                    and slider.winfo_rooty() <= y_root <= slider.winfo_rooty() + slider.height):
                slider.left_canvas = False
            else:
                slider.left_canvas = True


    def update_slider():
        # update current value of slider
        current_time = pd.Timestamp.now()
        if not stop_tvac_slider_update:
            tvac_slider.set_new_limits(end_value=current_time)
        if not stop_ths_slider_update:
            ths_slider.set_new_limits(end_value=current_time)


        root.after(1000, update_slider)


    def update_target_temp():
        global TVAC_Control, THS, last_autotune_time, new_target_temp, old_target_temp, waiting_for_autotuning  # cycle
        global last_target_set_time, sweep_interval, autotune_interval, autosweep_start_time, autosweep_start_temp, previous_temp_gradient  # sweep
        if THS.current_ths_mode is not None:
            # autocycle target temperature and autotune conditions
            if THS.current_ths_mode == 'autocycle' or THS.current_ths_mode == 'autocycle_non_stat':
                # get new target temp
                try:
                    new_target_temp = float(ths_list_input.get_current_value())
                except:
                    ths_output.delete(0, tk.END)
                    ths_output.insert(0, 'Could not get input_list value')
                    print(pd.Timestamp('now').strftime('%X'), 'Error getting new target temp')
                if new_target_temp != old_target_temp:
                    # update entry in gui
                    tvac_control_set_target_temp.delete(0, tk.END)
                    tvac_control_set_target_temp.insert(0, new_target_temp)
                    # autotune PID for next temperature
                    if not waiting_for_autotuning:
                        waiting_for_autotuning = True
                        threading_start_autotunePID()
                        last_autotune_time = pd.Timestamp('now')
                    # if autotuning was completed, set new target for PID heating, create new file beforehand
                    if TVAC_Control.autotuning_complete:
                        threading_set_target_temp()
                        # wait until TVAC target temp was set
                        if TVAC_Control.target_temp == new_target_temp:
                            waiting_for_autotuning = False
                            threading_start_PID()
                            # reset old temp for next temperature change
                            old_target_temp = new_target_temp
                            print(pd.Timestamp('now').strftime('%X'), 'Autotuning completed, new target set, PID started')
                else:
                    if last_autotune_time is not None:
                        # autotune once every hour
                        do_autotuning = False  # !!!!! AUTOMATIC AUTOTUNING CURRENTLY DISABLED !!!!!
                        if do_autotuning:  # pd.Timestamp('now') >= last_autotune_time + pd.Timedelta(1, 'h'):
                            # only autotune if temperature is not within 0.1K interval in last hour
                            if not TVAC_Control.temp_okay:
                                if not waiting_for_autotuning:
                                    waiting_for_autotuning = True
                                    threading_start_autotunePID()
                                    last_autotune_time = pd.Timestamp('now')
                                if TVAC_Control.autotuning_complete:
                                    waiting_for_autotuning = False

            # autosweep target temperature updates
            elif THS.current_ths_mode == 'autosweep':
                # check for new temperature gradient to recalculate new target temps
                if THS.temp_gradient != previous_temp_gradient:
                    autosweep_start_time = None
                    previous_temp_gradient = THS.temp_gradient
                # initiate autosweep starting conditions
                if autosweep_start_time is None:
                    autosweep_start_time = pd.Timestamp.now()
                    autosweep_start_temp = TVAC_Control.sample_holder_temp
                    if ths_list_input.values:
                        ths_list_input.mark_value(0)

                # set new target temp
                if pd.Timestamp.now() - last_target_set_time >= sweep_interval:
                    # calculate new target temp from starting time, temp and elapsed time + sweep interval
                    new_target_temp = (autosweep_start_temp +
                                       (pd.Timestamp.now() - autosweep_start_time +
                                        sweep_interval).total_seconds() / 60 / 60 * THS.temp_gradient)

                    autosweep_limit = ths_list_input.get_current_value()  # check for limit temperature input
                    if autosweep_limit is None:
                        autosweep_limit = 450

                    if new_target_temp <= 70 or new_target_temp > 450:  # check if new target temp is inside TVAC limits
                        error_out.delete(0, tk.END)
                        error_out.insert(0, 'Autosweep target temp outside allowed interval 70 - 450 K!')

                    elif ((THS.temp_gradient >= 0 and new_target_temp >= autosweep_limit) or
                          (THS.temp_gradient < 0 and new_target_temp <= autosweep_limit)):
                        # set new start conditions
                        autosweep_start_temp = TVAC_Control.sample_holder_temp
                        autosweep_start_time = pd.Timestamp.now()
                        # reverse temperature gradient for sweep
                        ths_temp_gradient_input.delete(0, tk.END)
                        ths_temp_gradient_input.insert(0, -1 * THS.temp_gradient)
                        error_out.delete(0, tk.END)
                        error_out.insert(0, f'THS gradient changed, limit reached {autosweep_limit}')
                        threading_set_ths_temp_gradient()
                        try:
                            ths_list_input.skip_value()  # go to next value in list input
                        except Exception as error:
                            print(pd.Timestamp.now().strftime('%X'), 'list input no value found', error)
                    else:
                        tvac_control_set_target_temp.delete(0, tk.END)
                        tvac_control_set_target_temp.insert(0, f'{new_target_temp:.3f}')
                        threading_set_target_temp()
                        last_target_set_time = pd.Timestamp.now()
                # make sure PID Control is active
                if not TVAC_Control.PID_active:
                    threading_start_PID()
                # automatically tune PID once every autotune_interval
                if pd.Timestamp.now() - last_autotune_time >= autotune_interval:
                    if not waiting_for_autotuning:
                        waiting_for_autotuning = True
                        threading_start_autotunePID()
                        last_autotune_time = pd.Timestamp('now')
                if TVAC_Control.autotuning_complete:
                    waiting_for_autotuning = False
            else:
                autosweep_start_time = None
                autosweep_start_temp = None

        root.after(10000, update_target_temp)  # update every 10 seconds


    def update_plots():
        try:
            plot_ths_data()
            plot_tvac_control_data()
        except Exception as error:
            print(pd.Timestamp.now().strftime('%X'), 'update_plots', error)
        root.after(2000, update_plots)


    def check_sdm():
        global SDM, last_sdm_stop_time, last_sdm_start_time, last_sdm_reset_time
        if SDM.need_reset is not None:
            if SDM.need_reset is True and TVAC_Control.running:
                time_now = pd.Timestamp('now').strftime('%X')
                error_out.delete(0, tk.END)
                error_out.insert(0, f'{time_now} SDM frozen')
                print('SDM needs reset')
                if pd.Timestamp('now') > last_sdm_stop_time + pd.Timedelta(2, 'min'):
                    threading_stop_sdm()
                    last_sdm_stop_time = pd.Timestamp('now')
                    print('Stopping SDM')
                if ((pd.Timestamp('now') > last_sdm_start_time + pd.Timedelta(2, 'min')) and
                        (pd.Timestamp('now') > last_sdm_stop_time + pd.Timedelta(30, 's'))):
                    threading_start_sdm()
                    last_sdm_start_time = pd.Timestamp('now')
                    print('Restarting SDM')
        if not SDM.active_measurement and SDM.active:
            if ((pd.Timestamp('now') > last_sdm_reset_time + pd.Timedelta(2, 'min')) and
                    (pd.Timestamp('now') > last_sdm_start_time + pd.Timedelta(30, 's'))):
                threading_sdm_start_tvac_measurement()
                threading_reset_SDM_instances()
                print('Resetting SDM TVAC measurement')
        if SDM.active_measurement:
            last_sdm_reset_time = pd.Timestamp('now')
        root.after(16000, check_sdm)


    def check_tvac_control():
        threading_tvac_control_check()
        root.after(10000, check_tvac_control)

    # update images and slider end values by time
    root.after(1000, update_slider)
    # implement slider click
    root.bind("<Button-1>", on_slider_click)

    root.after(2000, update_target_temp)

    root.after(2000, update_plots)

    root.after(2000, check_sdm)

    root.after(2000, check_tvac_control)

    root.after(1000, lambda: root.attributes('-topmost', False))

    root.mainloop()


except Exception as error:
    print(error)
    # catch any major exceptions and stop processes
    TVAC_Control.stop_tvac_control()
    THS.stop_THS()
    SDM.stop_device()
    rm.close()
    root.destroy()

