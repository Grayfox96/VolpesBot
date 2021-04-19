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

import socket
import time
import datetime
import math
import configparser
import re
from volpesbot_ui import *

class irc_bot:

	irc = socket.socket()
	ui = ui()
	# wait for the ui thread to complete the startup
	while not ui.waiting_for_ui.isSet():
		print("Waiting for UI")
		ui.waiting_for_ui.wait(2)
	print("UI open")
	chat_log = ""

	def __init__(self):
		# Define the socket
		self.irc = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
		self.handle = self.irc.makefile(mode='rw', buffering=1, encoding='utf-8', newline='\r\n')
		self.settings = configparser.ConfigParser()
		self.settings.read("files/irc_bot_settings.ini")
		self.server = self.settings["DEFAULT"]["server"]
		self.port = int(self.settings["DEFAULT"]["port"])
		self.bot_nick = self.settings["DEFAULT"]["bot_nick"]
		self.bot_user = self.settings["DEFAULT"]["bot_user"]
		self.bot_name = self.settings["DEFAULT"]["bot_name"]
		self.bot_owner = self.settings["DEFAULT"]["bot_owner"]
		try:
			self.bot_password_file = open("files/twitchoauth.txt", "r")
		except FileNotFoundError:
			self.bot_password_file = open("files/twitchoauth.txt", "x")
			self.log("Put your bot oauth in the 'twitchoauth.txt' file in this format: oauth:abcdefghijklmnopqrstuvwxyz1234")
			exit()
		self.bot_password = self.bot_password_file.read()
		self.bot_password_file.close()
		if re.match("^oauth:\w{30}$", self.bot_password):
			pass
		else:
			self.log("The 'twitchoauth.txt' file must contain the oauth token in the format: oauth:abcdefghijklmnopqrstuvwxyz1234")
			exit()

		# startup time used for uptime and stuff
		self.startup_time = time.time()

		# initialize the channels list
		self.connected_channels = []

		# compile the regex functions
		self.regex_message = re.compile("^@?(?P<tags>(?:[^\s=;]+=[^\s=;]*[; ])*)(?:\:(?P<nick>[^\!\@ ]+)(?:\!(?P<user>[^\@ ]+))?(?:\@(?P<host>[^ ]+))? )?(?P<cmd>[^ ]+)(?: (?P<channel>[^\:][^ ]*(?: [^\:][^ ]*)*))?(?: \:(?P<msg>.*))?$")

		# set an observer for the input box variable
		self.ui.message_out_var.trace("w", lambda a, b, c: self.send_raw(self.ui.message_out_var.get()))

	# connects to the server address and sends all the messages needed to connect to irc
	def connect(self):
		# Connect to the server
		self.log("Connecting to: " + self.server)
		self.irc.connect((self.server, self.port))
		# Perform user authentication
		self.send_raw("CAP REQ :twitch.tv/tags twitch.tv/commands")
		self.send_PASS(self.bot_password)
		self.send_raw("NICK " + self.bot_nick)
		self.send_raw("USER " + self.bot_user + " 0 * :" + self.bot_name)

	# accepts a string of channel names separated by commas
	def join(self, tags, nick, user, host, cmd, channel, msg, data, newchannel=""):
		# join the channels
		if newchannel:
			try:
				self.settings.add_section(newchannel)
				self.settings[newchannel]["connect_on_startup"] = "yes"
				self.send_raw("JOIN " + newchannel)
			except configparser.DuplicateSectionError:
				self.send_PRIVMSG(channel, "Already joined channel " + newchannel)
		else:
			channels = ""
			for temp_channel in self.settings.sections():
				if self.settings[temp_channel]["connect_on_startup"] == "yes":
					self.connected_channels.append(temp_channel)
					channels = channels + temp_channel + ","
			channels = channels.removesuffix(",")
			self.send_raw("JOIN " + channels)

	def part(self, tags, nick, user, host, cmd, channel, msg, data, removedchannel):
		self.connected_channels.remove(channel)
		self.settings[newchannel]["connect_on_startup"] == "no"
		self.send_raw("PART " + removedchannel)

	def log(self, data):
		current_time = datetime.datetime.now().strftime("%H:%M:%S")
		self.chat_log = self.chat_log + current_time + " " + data + "\n"
		self.ui.chat_log_text.set(self.chat_log.removesuffix("\n"))
		# print(data)

	# saves the setting in the settings file
	def save_settings(self):
			settings_file = open("files/irc_bot_settings.ini", "w")
			self.settings.write(settings_file)
			settings_file.close()
			self.log("Settings saved!")


	# send anything to the irc server, accepts a string
	def send_raw(self, message):
		self.log(">" + message)
		print(message, file=self.handle)

	# accepts a channel and some a string to send directly as a privmsg
	def send_PRIVMSG(self, channel, text):
		message = "PRIVMSG " + channel + " :" + text
		self.send_raw(message)

	# special "send_raw" case, this way the console doesnt receive the password as plain text
	def send_PASS(self, password):
		self.log(">PASS oauth:******************************")
		print("PASS", password, file=self.handle)

	# answers to a PING message with an appropriate PONG message
	def on_PING(self, tags, nick, user, host, cmd, channel, msg, data):
		self.send_raw("PONG :" + msg)
		# self.save_settings()

	# JOIN is not reliable so dont use it
	def on_JOIN(self, tags, nick, user, host, cmd, channel, msg, data):
		# self.connected_channels.append(channel)
		# self.send_PRIVMSG("#" + self.bot_nick, "Joined channel: " + channel)
		return

	# sends a message in the bot own channel every time it parts a channel
	# PART might not be reliable so dont use it for anything important
	def on_PART(self, tags, nick, user, host, cmd, channel, msg, data):
		# self.connected_channels.remove(channel)
		self.send_PRIVMSG("#" + self.bot_nick, "Parted channel: " + channel)

	# answers to a 376 message with a join message
	def on_376(self, tags, nick, user, host, cmd, channel, msg, data):
		self.join(tags, nick, user, host, cmd, channel, msg, data)

	def on_NOTICE(self, tags, nick, user, host, cmd, channel, msg, data):
		return
		# self.send_PRIVMSG(self.bot_nick, data)

	def on_PRIVMSG(self, tags, nick, user, host, cmd, channel, msg, data):
		# create a dictionary for the tags
		tags_dict = {}
		for tag in tags.split(";"):
			tag_split = tag.split("=")
			tags_dict[tag_split[0]] = tag_split[1]

		# check if a banned string is in the message
		if re.search("(?i)" + self.settings[channel]["banned_phrases"], msg) is not None:
			self.send_PRIVMSG(channel, "/delete " + tags_dict["id"])
			return

		# create the re.match object to be used in the if statements for the commands
		command_regex = "(?i)^" + self.settings[channel]["trigger"] + "(?P<command>\S+)(?:\s+(?P<param>.+?))?\s*$"
		full_command = {"command": "", "param": ""}
		full_command = re.match(command_regex, msg)

		# commands
		if full_command is not None:
			command = full_command["command"]
			param = full_command["param"]
			if nick == self.bot_owner:
				if command == "gettags": self.send_PRIVMSG(channel, data)
				elif command == "ping":
					uptime = math.floor(time.time() - self.startup_time)
					self.send_PRIVMSG(channel, "Uptime: " + str(datetime.timedelta(seconds=uptime)))
				elif command == "test": self.send_PRIVMSG(channel, "DankG")
				elif command == "joinchannel": self.join(tags, nick, user, host, cmd, channel, msg, data, newchannel="#" + param.split(" ")[0].lower())
				elif command == "partchannel": self.part(tags, nick, user, host, cmd, channel, msg, data, removedchannel="#" + param.split(" ")[0].lower())
				elif command == "banlist":
					params_list = param.split(" ", 2)
					start = int(params_list[0])
					limit = int(params_list[1])
					end = start + limit
					count = 0
					banlist_file = open("files/banlist.txt", "r")
					for banned_user in banlist_file.readlines():
						count +=1
						if count < start:
							continue
						elif count < end:
							self.send_PRIVMSG(channel, "/ban " + banned_user)
						else:
							self.send_PRIVMSG(channel, str(count))
							break
					banlist_file.close()
				elif command == "connectedchannels":
					response = ""
					for connected_channel in self.connected_channels:
						response = response + connected_channel + ", "
					response = "I'm connected to these channels: " + response.removesuffix(", ")
					self.send_PRIVMSG(channel, response)
				elif command == "quit":
					self.send_PRIVMSG(channel, "Closing script")
					self.ui.quit_var.set(True)
				elif command == "newcommand": return

			elif command: self.send_PRIVMSG(channel, "grayfoxWeirdDude frick off")