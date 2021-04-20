# VolpesBot, IRC bot for twitch.tv
# 	Copyright (C) 2021  Grayfox96

# 	This program is free software: you can redistribute it and/or modify
# 	it under the terms of the GNU General Public License as published by
# 	the Free Software Foundation, either version 3 of the License, or
# 	(at your option) any later version.

# 	This program is distributed in the hope that it will be useful,
# 	but WITHOUT ANY WARRANTY; without even the implied warranty of
# 	MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# 	GNU General Public License for more details.

# 	You should have received a copy of the GNU General Public License
# 	along with this program.  If not, see <https://www.gnu.org/licenses/>.

import tkinter as tk
from tkinter import messagebox
import threading

# Run tkinter code in another thread
class ui(threading.Thread):
	waiting_for_ui = threading.Event()

	def __init__(self):
		threading.Thread.__init__(self)
		self.start()

	def on_ui_close(self):
		if messagebox.askokcancel("Quit", "Do you want to quit?"):
			self.quit_var.set(True)

	def input_box_func(self, message):
		self.message_out_var.set(message)
		self.input_box_text.set("")

	def run(self):
		# create the root
		self.root = tk.Tk()
		# execute a function when the window is closed
		self.root.protocol("WM_DELETE_WINDOW", self.on_ui_close)
		self.root.title("VolpesBot\n")
		self.root.iconbitmap("files/VolpesBotTwitch.ico")
		self.root.geometry("800x800")

		# chat box
		self.chat_log_text = tk.StringVar()
		self.chat_log = tk.Label(self.root, bd=0, textvariable=self.chat_log_text, anchor="sw", justify="left", height=1)
		self.chat_log.pack(expand=True, fill="both")
		self.chat_log.bind("<Configure>", lambda e: self.chat_log.config(wraplength=self.chat_log.winfo_width()))

		# entry
		self.input_box_text = tk.StringVar()
		self.input_box = tk.Entry(self.root, width=1, textvariable=self.input_box_text)
		self.input_box.pack(expand=True, fill="x", anchor="sw", side="left")
		self.input_box.bind("<Return>", lambda e: self.input_box_func(self.input_box_text.get()))

		# button
		self.send_button = tk.Button(self.root, width=10, text="Send", command= lambda: self.input_box_func(self.input_box_text.get()))
		self.send_button.pack(anchor="se", side="right")

		# create the variable where to put the message to send
		self.message_out_var = tk.StringVar()

		# create the variable used to flag closing the program
		self.quit_var = tk.BooleanVar()

		# unpause the main thread and start the ui loop
		self.waiting_for_ui.set()
		self.root.mainloop()
