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
	def __init__(self):
		# Define the socket
		self.irc = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
		self.handle = self.irc.makefile(mode='rw', buffering=1, encoding='utf-8', newline='\r\n')

		# create the config object
		self.config = configparser.ConfigParser(allow_no_value=False, delimiters=("="), comment_prefixes=('#'), empty_lines_in_values=False)

		# try opening the settings file, if it doesnt exist create one
		try:
			with open("volpesbot_config.ini") as settings_file:
				self.config.read_file(settings_file)
		# if the file doesnt exist or cant be read
		except IOError:
			self._make_config_file()
		# making the settings variable names easier to use later
		self.server = self.config.get("DEFAULT", "server")
		self.port = self.config.getint("DEFAULT", "port")
		self.bot_nick = self.config.get("DEFAULT", "bot_nick")
		self.bot_user = self.config.get("DEFAULT", "bot_user")
		self.bot_name = self.config.get("DEFAULT", "bot_name")
		self.bot_owner = self.config.get("DEFAULT", "bot_owner")
		self.bot_password = self.config.get("DEFAULT", "bot_password")

		# create a variable used to store a temporary log, save the startup time, initialize the channels list
		self.session_variables = {
			"chat_log": "",
			"startup_time": time.time(),
			"connected_channels": []
		}

		# compile the regex functions
		self.regex_message = re.compile("^@?(?P<tags>(?:[^\s=;]+=[^\s=;]*[; ])*)(?:\:(?P<nick>[^\!\@ ]+)(?:\!(?P<user>[^\@ ]+))?(?:\@(?P<host>[^ ]+))? )?(?P<cmd>[^ ]+)(?: (?P<channel>[^\:][^ ]*(?: [^\:][^ ]*)*))?(?: \:(?P<msg>.*))?$")
		self.regex_pinged = re.compile("(?i)(?:\s|\A|\b)(@" + self.bot_nick + ")(?:\s|$|\b)")
		# create the ui
		self.ui = ui()
		# wait for the ui thread to complete the startup
		while not self.ui.waiting_for_ui.isSet():
			print("Waiting for UI")
			self.ui.waiting_for_ui.wait(2)
		print("UI open")
		# set an observer for the input box variable
		self.ui.message_out_var.trace("w", lambda a, b, c: self.send_raw(self.ui.message_out_var.get()))

	def _make_config_file(self):
		self.config.set("DEFAULT", "server", "irc.chat.twitch.tv")
		self.config.set("DEFAULT", "port", "6667")
		print("Enter the name of the bot account:")
		bot_nick_user_name = input(">").lower()
		self.config.set("DEFAULT", "bot_nick", bot_nick_user_name)
		self.config.set("DEFAULT", "bot_user", bot_nick_user_name)
		self.config.set("DEFAULT", "bot_name", bot_nick_user_name)
		print("Enter the name of your account (lets the bot know that you have full control over it):")
		bot_owner = input(">")
		self.config.set("DEFAULT", "bot_owner", bot_owner)
		print("Enter the oauth token for the bot account, it serves as a password, get it from here logging in with the bot account https://twitchapps.com/tmi/")
		bot_password = input(">")
		self.config.set("DEFAULT", "bot_password", bot_password)
		print("Enter the symbol you want the bot to respond to (for example ! or ?):")
		trigger = input(">")
		self.config.set("DEFAULT", "trigger", trigger)
		self.config.set("DEFAULT", "verbose_log", "not")
		# create a section for the bot owner and the bot itself
		self.config.add_section("#" + bot_nick_user_name)
		self.config.set("#" + bot_nick_user_name, "connect_on_startup", "yes")
		self.config.set("#" + bot_nick_user_name, "trigger", self.config.get("DEFAULT", "trigger"))
		self.config.add_section("#" + bot_owner)
		self.config.set("#" + bot_owner, "connect_on_startup", "yes")
		self.config.set("#" + bot_owner, "trigger", self.config.get("DEFAULT", "trigger"))
		self.save_settings()

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

	# passing a channel makes it connect to it, otherwise connects to all the channel in the settings
	def join(self, data, tags, nick, user, host, cmd, channel, msg, newchannel=None):
		# join the channels
		if newchannel is None:
			channels = ""
			for newchannel in self.config.sections():
				if self.config.getboolean(newchannel, "connect_on_startup"):
					print("Joining " + newchannel)
					self.session_variables["connected_channels"].append(newchannel)
					self.session_variables[newchannel] = {"last_mime_emote": 0}
					channels = channels + newchannel + ","
			channels = channels.removesuffix(",")
			self.send_raw("JOIN " + channels)
		else:
			# if the channel is in the settings
			if self.config.has_section(newchannel):
				# if already connected to the channel
				if newchannel in self.session_variables["connected_channels"]:
					return False
				# if not connected makes it connect on startup
				else:
					print("Joining " + newchannel)
					self.config.set(newchannel, "connect_on_startup", "yes")
					self.session_variables["connected_channels"].append(newchannel)
					self.send_raw("JOIN " + newchannel)
					return True
			# if not in the settings create a section for it
			else:
				self.config.add_section(newchannel)
				self.config.set(newchannel, "connect_on_startup", "yes")
				self.config.set(newchannel, "trigger", self.config.get("DEFAULT", "trigger"))
				self.session_variables["connected_channels"].append(newchannel)
				self.send_raw("JOIN " + newchannel)
				return True

	# parts a channel
	def part(self, data, tags, nick, user, host, cmd, channel, msg, removedchannel):
		# if connected to that channel removes it from startup
		if removedchannel in self.session_variables["connected_channels"]:
			print("Leaving " + removedchannel)
			self.session_variables["connected_channels"].remove(removedchannel)
			self.config.set(removedchannel, "connect_on_startup", "no")
			self.send_raw("PART " + removedchannel)
			return True
		else:
			return False

	# outputs to the log
	def log(self, data, tags="", nick="", user="", host="", cmd="", channel="", msg=""):
		current_time = datetime.datetime.now().strftime("%H:%M:%S")
		# in this case outputs everything
		if self.config.getboolean("DEFAULT", "verbose_log"):
			self.session_variables["chat_log"] = f"{self.session_variables['chat_log']} {current_time} {data}\n"
		# in this case only PRIVMSG
		elif cmd == "PRIVMSG":
			self.session_variables["chat_log"] = f"{self.session_variables['chat_log']}{current_time} <{channel}> {user}: {msg}\n"
		self.ui.chat_box_text.set(self.session_variables["chat_log"].removesuffix("\n"))
		# print(data)

	# saves the setting in the settings file
	def save_settings(self):
		try:
			with open("volpesbot_config.ini", "w") as settings_file:
				self.config.write(settings_file)
		except IOError:
			print("Unable to save settings!")
		else:
			print("Settings saved!")

	# send anything to the irc server, accepts a string
	def send_raw(self, message):
		self.log(">" + message)
		# this writes to the socket file
		print(message, file=self.handle)

	# accepts a channel and a string to send directly as a privmsg
	def send_PRIVMSG(self, channel, text):
		message = "PRIVMSG " + channel + " :" + text
		# this writes to the socket file
		self.send_raw(message)

	# special "send_raw" case, this way the console doesnt output the password as plain text
	def send_PASS(self, password):
		self.log(">PASS oauth:******************************")
		print("PASS", password, file=self.handle)

	# answers to a PING message with a PONG message
	def on_PING(self, data, tags, nick, user, host, cmd, channel, msg):
		self.send_raw("PONG :" + msg)
		# self.save_settings()

	# sends a message in the bot own channel every time it joins a channel
	# JOIN is not reliable when connecting to 2+ channels, the server doesnt send JOIN messages for all the channels
	def on_JOIN(self, data, tags, nick, user, host, cmd, channel, msg):
		# self.session_variables["connected_channels"].append(channel)
		# self.send_PRIVMSG("#" + self.bot_nick, "Joined channel: " + channel)
		pass

	# sends a message in the bot own channel every time it parts a channel
	# PART might not be reliable so dont use it for anything important
	def on_PART(self, data, tags, nick, user, host, cmd, channel, msg):
		# self.session_variables["connected_channels"].remove(channel)
		self.send_PRIVMSG("#" + self.bot_nick, "Parted channel: " + channel)
		pass

	# answers to a 376 message with a join message
	def on_376(self, data, tags, nick, user, host, cmd, channel, msg):
		self.join(data, tags, nick, user, host, cmd, channel, msg)

	def on_NOTICE(self, data, tags, nick, user, host, cmd, channel, msg):
		self.send_PRIVMSG("#" + self.bot_nick, data)
		pass

	def on_PRIVMSG(self, data, tags, nick, user, host, cmd, channel, msg):
		# create a dictionary for the tags
		tags_dict = {}
		for tag in tags.split(";"):
			tag_split = tag.split("=")
			tags_dict[tag_split[0]] = tag_split[1]

		# check if the bot is setup to delete messages
		if self.config.has_option(channel, "banned_phrases"):
			# check if a banned string is in the message
			if re.search("(?i)" + self.config.get(channel, "banned_phrases"), msg) is not None:
				self.send_PRIVMSG(channel, "/delete " + tags_dict["id"])
				print("Message deleted from user " + user + ", message content: " + msg)
				return

		# check if the bot is setup to copy specific emotes
		if self.config.has_option(channel, "mime_emotes"):
			# check if the emote is in the message
			mime_emotes_result = re.search("(?:\s|\A|\b)(?P<emote>" + self.config.get(channel, "mime_emotes") + ")(?:\s|$|\b)", msg)
			if mime_emotes_result is not None:
				cooldown = self.config.getint(channel, "mime_emotes_cooldown", fallback=30)
				if (int(self.session_variables[channel]["last_mime_emote"]) + self.config.getint(channel, "mime_emotes_cooldown") - int(tags_dict["tmi-sent-ts"])) < 0:
					self.session_variables[channel]["last_mime_emote"] = tags_dict["tmi-sent-ts"]
					self.send_PRIVMSG(channel, mime_emotes_result["emote"])



		# check if the bot has been pinged
		if self.regex_pinged.search(msg) is not None:
			self.send_PRIVMSG(channel, "👋 FeelsDankMan hi " + tags_dict["display-name"] + "! I'm a bot.")

		# create the re.match object to be used in the if statements for the commands
		command_regex = "(?i)^" + self.config.get(channel, "trigger") + "(?P<command>\S+)(?:\s+(?P<param>.+?))?\s*$"
		# full_command = {"command": "", "param": ""}
		full_command = re.match(command_regex, msg)

		# commands
		if full_command is not None:
			command = full_command["command"]
			param = full_command["param"]
			if nick == self.bot_owner:
				if command == "gettags": self.send_PRIVMSG(channel, data)
				elif command == "ping":
					uptime = math.floor(time.time() - self.session_variables["startup_time"])
					self.send_PRIVMSG(channel, "Uptime: " + str(datetime.timedelta(seconds=uptime)))
				elif command == "test": self.send_PRIVMSG(channel, "DankG")
				elif command == "joinchannel":
					newchannel = "#" + param.split()[0].lower()
					if self.join(data, tags, nick, user, host, cmd, channel, msg, newchannel):
						self.send_PRIVMSG(channel, "Joined channel " + newchannel)
					else:
						self.send_PRIVMSG(channel, "Already joined channel " + newchannel)
				elif command == "partchannel" or command == "leavechannel":
					removedchannel = "#" + param.split()[0].lower()
					if removedchannel == "#" + self.bot_nick:
						self.send_PRIVMSG(channel, "I can't leave my own channel, if you don't want me to join this chat on startup edit the settings file")
					elif removedchannel == channel:
						self.send_PRIVMSG(channel, "If you want me to leave this chat use the command in my chat")
					else:
						if self.part(data, tags, nick, user, host, cmd, channel, msg, removedchannel=removedchannel):
							self.send_PRIVMSG(channel, "Left channel " + removedchannel)
						else:
							self.send_PRIVMSG(channel, "I'm not connected to channel " + removedchannel)
				elif command == "banlist":
					params_list = param.split(maxsplit=2)
					start = int(params_list[0])
					limit = int(params_list[1])
					end = start + limit
					count = 0
					try:
						with open("banlist.txt", "r") as banlist_file:
							for banned_user in banlist_file.readlines():
								count +=1
								if count < start:
									continue
								elif count < end:
									self.send_PRIVMSG(channel, "/ban " + banned_user)
								else:
									self.send_PRIVMSG(channel, str(count))
									break
					except IOError:
						self.send_PRIVMSG(channel, "Can't find or access file banlist.txt")
				elif command == "connectedchannels":
					response = ""
					for connected_channel in self.session_variables["connected_channels"]:
						response = response + connected_channel + ", "
					response = "I'm connected to these channels: " + response.removesuffix(", ")
					self.send_PRIVMSG(channel, response)
				elif command == "quit":
					self.send_PRIVMSG(channel, "Closing script")
					self.ui.quit_var.set(True)
				elif command == "newcommand": pass
			elif command: self.send_PRIVMSG(channel, "grayfoxWeirdDude frick off")
