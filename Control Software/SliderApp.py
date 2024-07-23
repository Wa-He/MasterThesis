# -*- coding: utf-8 -*-
"""
Created on Mon Sep  4 09:42:41 2023

@author: henni
"""
import tkinter as tk
import pandas as pd


class IntervalSliderApp(tk.Canvas):
    def __init__(self, master, width, height=100, slider_scale=0.2, start_value=0,
                 end_value=100):  # master=root, kwargs = width, height, ..
        self.master = master
        self.height = height
        self.width = width

        super().__init__(self.master, width=self.width, height=self.height)  # initialize outer Canvas

        # define and place slider box
        self.slider_box_x0 = slider_scale * self.width
        self.slider_box_x1 = self.width - self.slider_box_x0
        self.slider_box_y0 = 0.001 * self.width
        self.slider_box_y1 = self.height
        self.slider_box_width = self.slider_box_x1 - self.slider_box_x0
        self.slider_box = self.create_rectangle(self.slider_box_x0, self.slider_box_y0, self.slider_box_x1,
                                                self.slider_box_y1, fill='lightgray')

        # define and place entries
        self.entry_start = tk.Entry(self, width=17)
        self.entry_end = tk.Entry(self, width=17)
        self.entry_start.place(x=width * 0.01, y=0.5 * self.slider_box_y1, anchor='w')
        self.entry_end.place(x=width * 0.99, y=0.5 * self.slider_box_y1, anchor='e')

        # register click on entries to start assigning values
        self.entry_start.bind("<Button-1>", lambda event: self.entry_click(event, self.entry_start))
        self.entry_end.bind("<Button-1>", lambda event: self.entry_click(event, self.entry_end))
        self.entry_start.bind("<Return>", self.on_return)
        self.entry_end.bind("<Return>", self.on_return)
        # register click on canvas to update assignment

        # initialize slider
        self.active_entry = None  # initialized value to track active entry
        self.selected_start_rel = 0  # initialized relative interval start
        self.selected_end_rel = 100  # initialized relative interval end
        self.start_value = start_value  # initialize absolute interval start
        self.end_value = end_value  # initialize absolute interval end
        self.interval = end_value - start_value  # calculate absolute interval size

        self.click_value = None
        self.left_canvas = False

        self.update_entry_values()
        self.draw_slider()

    def entry_click(self, event, entry_widget):
        if entry_widget == self.entry_start:
            self.currently_editing = 'start'
        elif entry_widget == self.entry_end:
            self.currently_editing = 'end'
        # start to register hover and click
        if self.currently_editing is not None:
            self.bind("<Motion>", self.on_hover)
            self.bind("<Button-1>", self.on_click)

    def on_hover(self, event):
        if self.currently_editing is not None and not self.left_canvas:
            if self.canvasy(event.y) >= self.slider_box_y0 and self.canvasy(event.y) <= self.slider_box_y1:
                x = self.canvasx(event.x)
                x = x - self.slider_box_x0
                self.left_canvas = False
                if x >= 0 and x <= self.slider_box_width:
                    self.hovered_value_rel = x
                elif x <= -0.25 * self.slider_box_x0 and x >= self.width + 0.25 * self.slider_box_x0:
                    self.left_canvas = True
                elif x < 0:
                    self.hovered_value_rel = 0
                elif x > self.slider_box_width:
                    self.hovered_value_rel = self.slider_box_width
            else:
                self.hovered_value_rel = None
            self.show_hover_values()

    def on_click(self, event):
        if self.currently_editing is not None:
            x = self.canvasx(event.x)
            x = x - self.slider_box_x0
            if self.canvasy(event.y) >= self.slider_box_y0 and self.canvasy(event.y) <= self.slider_box_y1:
                if x >= 0 and x <= self.slider_box_width:
                    self.click_value = x
                elif x < 0 and x >= -0.25 * self.slider_box_width:
                    self.click_value = 0
                elif x > self.slider_box_width and x <= 1.25 * self.slider_box_width:
                    self.click_value = self.slider_box_width
            if self.left_canvas == True:
                self.draw_slider()
                self.currently_editing = None
            if self.click_value is not None:
                if self.currently_editing == 'start':
                    self.selected_start_rel = self.click_value / self.slider_box_width * 100
                elif self.currently_editing == 'end':
                    self.selected_end_rel = self.click_value / self.slider_box_width * 100
                self.currently_editing = None
            self.update_entry_values()

    def on_return(self, event):
        if self.currently_editing is not None:
            try:
                if self.currently_editing == 'start':
                    self.selected_start_rel = self.format_input(self.entry_start.get())
                elif self.currently_editing == 'end':
                    self.selected_end_rel = self.format_input(self.entry_end.get())
            except Exception as error:
                print(pd.Timestamp('now').strftime('%X'), 'SliderAPP:', error)
            self.currently_editing = None
            self.update_entry_values()

    def show_hover_values(self):
        if self.hovered_value_rel is not None:
            self.hovered_value_abs = self.get_absolute_values(self.hovered_value_rel / self.slider_box_width * 100)
            if self.currently_editing == "start":
                self.entry_start.delete(0, tk.END)
                self.entry_start.insert(0, self.format_output(self.hovered_value_abs))
            if self.currently_editing == "end":
                self.entry_end.delete(0, tk.END)
                self.entry_end.insert(0, self.format_output(self.hovered_value_abs))
        else:
            self.update_entry_values()

    def update_entry_values(self):
        if self.selected_end_rel <= self.selected_start_rel:
            return
        self.selected_start_abs = self.get_absolute_values(self.selected_start_rel)
        self.selected_end_abs = self.get_absolute_values(self.selected_end_rel)
        self.entry_start.delete(0, tk.END)
        self.entry_start.insert(0, self.format_output(self.selected_start_abs))
        self.entry_end.delete(0, tk.END)
        self.entry_end.insert(0, self.format_output(self.selected_end_abs))
        self.draw_slider()

    def draw_slider(self):
        # delete old slider
        self.delete("all")
        self.slider_box = self.create_rectangle(self.slider_box_x0, self.slider_box_y0, self.slider_box_x1,
                                                self.slider_box_y1, fill='lightgray')
        # draw new slider based on selected values and slider box positions
        self.slider_x0 = self.slider_box_x0 + (self.selected_start_rel / 100 * self.slider_box_width)
        self.slider_x1 = self.slider_box_x0 + (self.selected_end_rel / 100 * self.slider_box_width)
        self.slider_y0 = self.slider_box_y0
        self.slider_y1 = self.slider_box_y1
        self.slider_foreground = self.create_rectangle(self.slider_x0, self.slider_y0, self.slider_x1, self.slider_y1,
                                                       fill='black')

        self.current_start = self.selected_start_abs
        self.current_end = self.selected_end_abs

    def set_new_limits(self, start_value=None, end_value=None):
        # update limits only if current limits are maxed out respectively
        if start_value is not None and self.selected_start_rel == 0:
            self.start_value = start_value
            self.interval = self.end_value - self.start_value
            self.entry_start.delete(0, tk.END)
            self.entry_start.insert(0, self.format_output(start_value))
            self.selected_start_abs = self.get_absolute_values(self.selected_start_rel)
        if end_value is not None and self.selected_end_rel == 100:
            self.end_value = end_value
            self.interval = self.end_value - self.start_value
            self.entry_end.delete(0, tk.END)
            self.entry_end.insert(0, self.format_output(end_value))
            self.selected_end_abs = self.get_absolute_values(self.selected_end_rel)
        self.draw_slider()

    def get_absolute_values(self, relative_values):
        # calculate absolute from relative values
        if relative_values is not None:
            return relative_values / 100 * self.interval + self.start_value

    def format_output(self, value_to_format):
        # format number to time or float
        if isinstance(value_to_format, pd.Timestamp):
            return str(value_to_format.floor('s').strftime('%Y-%m-%d %H:%M:%S'))
        elif isinstance(value_to_format, float):
            return f'{value_to_format:.1f}'
        else:
            return str(value_to_format)

    def format_input(self, input_value):
        # format input value
        try:
            timestamp = pd.Timestamp(input_value)
            if self.start_value <= timestamp <= self.end_value:
                return (timestamp - self.start_value) / self.interval * 100
        except Exception as e:
            print(e)
            pass
        return (float(input_value) - self.start_value) / self.interval * 100