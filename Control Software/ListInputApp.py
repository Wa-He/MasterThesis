# -*- coding: utf-8 -*-
import tkinter as tk
import customtkinter as ctk
from tkinter import messagebox as mb


class ListInputApp(ctk.CTkFrame):
    def __init__(self, root, width=500, height=1000, entry_style={}, label_style={}, button_style={}):
        super().__init__(root, width=width, height=height)  # Set the width and height of the container
        self.configure(fg_color=root.cget('fg_color'))
        self.entry_style = entry_style
        self.label_style = label_style
        self.button_style = button_style

        self.values = []  # List to store entered values

        self.grid_rowconfigure(0, weight=0)
        self.grid_rowconfigure(1, weight=1, minsize=50)
        self.grid_rowconfigure(2, weight=0)
        self.grid_columnconfigure(3, weight=0)

        # Entry
        self.entry = ctk.CTkEntry(self, **self.entry_style)
        self.entry.grid(row=0, column=0, columnspan=2, rowspan=1, sticky='ew')
        self.entry.bind("<Return>", self.add_value_on_enter)  # Bind the Return key
        # Add value button
        self.add_button = ctk.CTkButton(self, text=" Add ", command=self.add_value, width=20, **self.button_style)
        self.add_button.grid(row=0, column=2, columnspan=2, rowspan=1, padx=(5, 0))
        # Listbox to display entered values
        self.listbox = tk.Listbox(self, bg=self.entry.cget('fg_color')[1], fg=self.entry.cget('text_color')[1],
                                  highlightbackground=self.entry.cget('fg_color')[1], relief="flat")
        self.listbox.grid(row=1, column=0, columnspan=3, rowspan=1, sticky='nsew', pady=5)

        # Vertical scrollbar for Listbox
        self.listbox_scrollbar = ctk.CTkScrollbar(self, orientation='vertical', command=self.listbox.yview,
                                                  corner_radius=10)
        self.listbox_scrollbar.grid(row=1, column=3, columnspan=1, rowspan=1)
        self.listbox.configure(yscrollcommand=self.listbox_scrollbar.set)

        # clear values button
        self.clear_values_button = ctk.CTkButton(self, text="Clear", command=self.clear_listbox, width=20,
                                                 **button_style)
        self.clear_values_button.grid(row=2, column=2, columnspan=2, rowspan=1, sticky='e')

        # skip value button
        self.skip_value_button = ctk.CTkButton(self, text='Skip', command=self.skip_value, width=20, **button_style)
        self.skip_value_button.grid(row=2, column=0, columnspan=2, rowspan=1, sticky='w')

        # Configure grid weights to make the Listbox expand horizontally and vertically
        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(0, weight=1)

        self.mark_index = None
        self.currently_marked_value = None

    def add_value(self):
        # add a value from entry to listbox
        value = self.entry.get()
        try:
            value = value.replace(',', '.')
            value = float(value)
        except:
            value = None
        if value:  # Check if entry is not empty
            self.values.append(value)
            self.entry.delete(0, tk.END)
            self.update_listbox()
            self.mark_value()

    def add_value_on_enter(self, event):
        # call add_value after return key was pressed from entry field
        self.add_value()

    def get_values(self):
        # return all values currently within listbox
        return self.values

    def update_listbox(self):
        # clear listbox and add values to update
        self.listbox.delete(0, tk.END)
        for value in self.values:
            self.listbox.insert(tk.END, value)
        self.listbox.configure(bg=self.entry.cget('fg_color')[1])

    def clear_listbox(self):
        # clear listbox and values
        answer = mb.askyesno('Clear Listbox', 'Are you sure you want to clear?\nThis might influence active processes!',
                             default='no')
        if answer == True:
            self.reset_marking()
            self.listbox.delete(0, tk.END)
            self.values = []
            self.mark_index = None
            self.currently_marked_value = None

    def mark_value(self, mark_index=-1):
        # change color of a singular item in the list based on listbox index
        self.reset_marking()
        if mark_index != -1:
            self.mark_index = mark_index
        if self.mark_index is not None:
            self.listbox.itemconfig(self.mark_index, {'bg': 'gray'})  # Change the background color of the selected item
            self.currently_marked_value = self.values[self.mark_index]

    def skip_value(self):
        if self.mark_index is not None:
            self.mark_index += 1
            self.reset_marking()
            self.mark_value()

    def reset_marking(self):
        try:
            bg_color = self.entry.cget('fg_color')[1]
            self.get_values()
            for ii in range(len(self.values)):
                self.listbox.itemconfig(ii, {'bg': bg_color})
        except Exception as error:
            print(error)

    def get_current_value(self):
        return self.currently_marked_value
