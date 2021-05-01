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
import datetime

# Run tkinter code in another thread
class UI(threading.Thread):

	def __init__(self):
		self.ui_ready = threading.Event()
		self.quit_var = threading.Event()
		self.restart_var = threading.Event()
		threading.Thread.__init__(self)
		self.start()

	def on_ui_close(self):
		if messagebox.askokcancel("Quit", "Do you want to quit?"):
			if threading.main_thread().is_alive():
				self.quit_var.set()
			else:
				self.root.destroy()

	def input_box_func(self, message):
		self.message_out_var.set(message)
		self.input_box_text.set("")

	def run(self):
		# create the root
		self.root = tk.Tk()
		# execute a function when the window is closed
		self.root.protocol("WM_DELETE_WINDOW", self.on_ui_close)
		self.root.title("VolpesBot")
		self.root.iconbitmap("files/VolpesBotTwitch.ico")
		self.root.geometry("800x800")

		# chat box canvas
		self.chat_box_canvas = tk.Canvas(self.root)
		self.chat_box_canvas.pack(expand=True, fill="both")

		# chat box
		self.chat_box = tk.Text(self.chat_box_canvas, state="disabled", wrap="word")
		self.chat_box.pack(expand=True, fill="both", side="left")

		# chat box scrollbar
		self.chat_box_scrollbar = tk.Scrollbar(self.chat_box_canvas, orient = "vertical", command = self.chat_box.yview)
		self.chat_box_scrollbar.pack(fill="y", anchor="e", side="right")

		# connect the chat box movement to the scrollbar
		self.chat_box.configure(yscrollcommand=self.chat_box_scrollbar.set)

		# add tag objects to the chat box
		self.chat_box.tag_configure("gray", foreground="#888888")
		self.chat_box.tag_configure("underline", underline=True)
		self.chat_box.tag_configure("black", foreground="#000000")
		self.chat_box.tag_configure("warning", foreground="#ff3333")
		self.chat_box.tag_configure("blue", foreground="#3333ff")
		self.chat_box.tag_configure("wrap_char", wrap="char")

		# entry
		self.input_box_text = tk.StringVar()
		self.input_box = tk.Entry(self.root, width=1, textvariable=self.input_box_text)
		self.input_box.pack(expand=True, fill="x", anchor="sw", side="left")
		self.input_box.bind("<Return>", lambda e: self.input_box_func(self.input_box_text.get()))

		# send button
		self.send_button = tk.Button(self.root, width=10, text="Send", command= lambda: self.input_box_func(self.input_box_text.get()))
		self.send_button.pack(anchor="se", side="right")

		# create the variable where to store the message to send
		self.message_out_var = tk.StringVar()

		# unpause the main thread and start the ui loop
		self.ui_ready.set()
		self.root.mainloop()

	def print_PRIVMSG(self, channel, nick, message, nick_color="#000000"):

		# add some padding around the text
		nick = " " + nick + ": "

		# if the tag for the specific nick color doesnt exist create one
		if nick_color in self.chat_box.tag_names():
			pass
		else:
			self.chat_box.tag_configure(nick_color, foreground=nick_color)

		self._print(channel, "underline", nick, nick_color, f"{message}\n", "black")


	def print_warning(self, message):
		self._print(message + "\n", "warning")


	def print_info(self, message):
		self._print(message + "\n", "blue")


	def print_NOTICE(self, channel, message):
		self._print(channel , ("black", "underline") , f"{message}\n", "blue")


	def print_log(self, message):
		self._print(f"{message}\n", ("gray", "wrap_char"))


	def _print(self, *args):
		# get the formatted time and make some padding around the text
		current_time = datetime.datetime.now().strftime("%H:%M:%S") + " "

		self.chat_box.config(state="normal")
		self.chat_box.insert("end", current_time, "gray", *args)
		self.chat_box.config(state="disabled")
		self.chat_box.see("end")