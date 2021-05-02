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

import os
import sys
import socket
import time
import datetime
import math
import configparser
import re
import threading
from volpesbot_ui import *
from tokenbucket import *


class IRCBot:

	class AuthorizationError(Exception): pass


	def __init__(self):
		# Define the socket
		self.irc = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
		self.handle = self.irc.makefile(mode="rw", buffering=1, encoding="utf-8", newline="\r\n")

		# create the config object
		self.config = configparser.ConfigParser(allow_no_value=False, delimiters=("="), comment_prefixes=("#"), empty_lines_in_values=False)

		# try opening the settings file, if it doesnt exist create one
		try:
			with open("volpesbot_config.ini") as settings_file:
				self.config.read_file(settings_file)

		# if the file doesnt exist or cant be read
		except IOError:
			print("Settings file not found, follow the instructions to create one.")
			self._make_config_file()

		# making the settings variable names easier to use later
		self.server = self.config.get("DEFAULT", "server")
		self.port = self.config.getint("DEFAULT", "port")
		self.bot_nick = self.config.get("DEFAULT", "bot_nick")
		self.bot_user = self.config.get("DEFAULT", "bot_user")
		self.bot_name = self.config.get("DEFAULT", "bot_name")
		self.bot_owner = self.config.get("DEFAULT", "bot_owner")
		self.bot_password = self.config.get("DEFAULT", "bot_password")

		# make a dict used to store session information
		self.session_variables = {
			"startup_time": time.time(),
			"connected_channels": []
		}

		# initialize the token bucket
		self.token_bucket = TokenBucket(100, 30)

		# compile the regex functions
		self.regex_message = re.compile("^@?(?P<tags>(?:[^\s=;]+=[^\s=;]*[; ])*)"
										"(?:\:(?P<nick>[^\!\@ ]+)(?:\!(?P<user>[^\@ ]+))?(?:\@(?P<host>[^ ]+))? )?"
										"(?P<cmd>[^ ]+)"
										"(?: (?P<channel>[^\:][^ ]*(?: [^\:][^ ]*)*))?"
										"(?: \:(?P<msg>.*))?$")
		self.regex_pinged = re.compile("(?i)(?:\s|\A|\b)(@" + self.bot_nick + ")(?:\s|$|\b)")
		# https://mathiasbynens.be/demo/url-regex
		self.regex_url = re.compile("(?i)(?:\s|\A|\b)(?:(?:https?://)?(?P<url>(?:[^\s/$.?#][^\s/]*)(\.[^.\s]+)))(?:\s|\A|\b)")
		# create the ui
		self.ui = UI()
		# wait for the ui thread to complete the startup
		while not self.ui.ui_ready.isSet():
			print("Waiting for UI")
			self.ui.ui_ready.wait(2)
		print("UI open")

		# set an observer for the input box variable
		self.ui.message_out_var.trace("w", lambda a, b, c: self.send_raw(self.ui.message_out_var.get()))


	def _make_config_file(self):
		self.config.set("DEFAULT", "server", "irc.chat.twitch.tv")
		self.config.set("DEFAULT", "port", "6667")
		bot_nick_user_name = input("Enter the name of the bot account:").lower()
		self.config.set("DEFAULT", "bot_nick", bot_nick_user_name)
		self.config.set("DEFAULT", "bot_user", bot_nick_user_name)
		self.config.set("DEFAULT", "bot_name", bot_nick_user_name)
		bot_owner = input("Enter the name of your account (lets the bot know who has full control over it):")
		self.config.set("DEFAULT", "bot_owner", bot_owner)
		bot_password = input("Enter the oauth token for the bot account (get it from here logging in with the bot account https://twitchapps.com/tmi/):")
		self.config.set("DEFAULT", "bot_password", bot_password)
		trigger = input("Enter the symbol you want the bot to respond to (for example ! or ?):")
		self.config.set("DEFAULT", "trigger", trigger)
		self.config.set("DEFAULT", "verbose_log", "no")
		# create a section for the bot owner and the bot itself
		self.config.add_section(f"#{bot_nick_user_name}")
		self.config.set(f"#{bot_nick_user_name}", "connect_on_startup", "yes")
		self.config.set(f"#{bot_nick_user_name}", "trigger", self.config.get("DEFAULT", "trigger"))
		self.config.add_section(f"#{bot_owner}")
		self.config.set(f"#{bot_owner}", "connect_on_startup", "yes")
		self.config.set(f"#{bot_owner}", "trigger", self.config.get("DEFAULT", "trigger"))
		self.save_settings()


	# connects to the server address and sends all the messages needed to connect to irc
	def connect(self):
		# Connect to the server
		self.log(f"Connecting to: {self.server}", cmd="info")
		self.irc.connect((self.server, self.port))
		# Perform user authentication
		self.send_raw("CAP REQ :twitch.tv/tags twitch.tv/commands")
		self.send_PASS(self.bot_password)
		self.send_raw(f"NICK {self.bot_nick}")
		self.send_raw(f"USER {self.bot_user} 0 * :{self.bot_name}")


	# passing a channel makes it connect to it, otherwise connects to all the channel in the settings
	def _join(self, data, tags, nick, user, host, cmd, channel, msg, newchannel=None):
		# join the channels
		if newchannel is None:
			channels = ""
			for newchannel in self.config.sections():
				if self.config.getboolean(newchannel, "connect_on_startup"):
					self.session_variables["connected_channels"].append(newchannel)
					self.session_variables[newchannel] = {"last_mime_emote": 0}
					channels = channels + newchannel + ","
			channels = channels.removesuffix(",")
			self.send_raw(f"JOIN {channels}")
			self.log(f"Connected to {channels}", cmd="info")
		else:
			# if the channel is in the settings
			if self.config.has_section(newchannel):
				# if already connected to the channel
				if newchannel in self.session_variables["connected_channels"]:
					return False
				# if not connected makes it connect on startup
				else:
					self.log(f"Joining {newchannel}", cmd="info")
					self.config.set(newchannel, "connect_on_startup", "yes")
					self.session_variables["connected_channels"].append(newchannel)
					self.send_raw(f"JOIN {newchannel}")
					return True
			# if not in the settings create a section for it
			else:
				self.config.add_section(newchannel)
				self.config.set(newchannel, "connect_on_startup", "yes")
				self.config.set(newchannel, "trigger", self.config.get("DEFAULT", "trigger"))
				self.session_variables["connected_channels"].append(newchannel)
				self.send_raw(f"JOIN {newchannel}")
				return True


	# parts a channel
	def _part(self, data, tags, nick, user, host, cmd, channel, msg, removedchannel):
		# if connected to that channel removes it from startup
		if removedchannel in self.session_variables["connected_channels"]:
			self.log(f"Parting {removedchannel}", cmd="info")
			self.session_variables["connected_channels"].remove(removedchannel)
			self.config.set(removedchannel, "connect_on_startup", "no")
			self.send_raw(f"PART {removedchannel}")
			return True
		else:
			return False


	# outputs to the log
	def log(self, data, tags="", nick="", user="", host="", cmd="", channel="", msg=""):

		# print everything to the ui only if verbose log is active
		if self.config.getboolean("DEFAULT", "verbose_log"):
			self.ui.print_log(data)

		# these cmds are always printed with specific formatting
		if cmd == "PRIVMSG":
			# get the nick color from the tags
			nick_color = "".join([tag.split("=")[1] for tag in tags.split(";") if tag.split("=")[0] == "color"])
			self.ui.print_PRIVMSG(channel, nick, msg, nick_color)
		elif cmd == "WHISPER":
			nick_color = "".join([tag.split("=")[1] for tag in tags.split(";") if tag.split("=")[0] == "color"])
			self.ui.print_WHISPER(nick, msg, nick_color)
		elif cmd == "NOTICE":
			self.ui.print_NOTICE(channel, msg)
		# not an actual IRC command, used internally to print these messages in a different style
		elif cmd == "warning":
			self.ui.print_warning(data)
		# a real irc command but not supported by twitch, used internally to print these messages in a different style
		elif cmd == "info":
			self.ui.print_info(data)


	# saves the setting in the settings file
	def save_settings(self):
		try:
			with open("volpesbot_config.ini", "w") as settings_file:
				self.config.write(settings_file)
		except IOError:
			self.log("IOError: Unable to save settings!", cmd="warning")
		else:
			self.log("Settings saved!", cmd="info")


	def quit(self):
		print("Closing script")
		# save the settings in the settings file
		self.save_settings()
		# close the ui (its running in different thread)
		self.ui.root.quit()
		print("You can now close this window")
		# close the program
		quit()


	def restart(self):
		print("Restarting script")
		# save the settings in the settings file
		self.save_settings()
		# close the ui (its running in different thread)
		self.ui.root.quit()
		# print some info
		print("sys.argv was", sys.argv)
		print("sys.executable was", sys.executable)
		print("Restarting now")
		# restart the program
		os.execv(sys.executable, ["python"] + sys.argv)


	# send anything to the irc server, accepts a string
	def send_raw(self, message):
		send_raw_regex = "^(?P<command>[A-Z ]*)(?: )(?P<channel>#[^\s]*)?(?: ?:?(?P<msg>.*))?$"
			# CAP REQ :twitch.tv/tags twitch.tv/commands
			# PASS oauth:******************************
			# NICK volpesbot
			# USER volpesbot 0 * :volpesbot
			# JOIN #volpesbot,#grayfox1996
			# PRIVMSG #volpesbot :test
			# PONG :tmi.twitch.tv
		matches_tuple = re.match(send_raw_regex, message)
		if matches_tuple is not None:
			self.log(message, nick=self.bot_nick, cmd=matches_tuple["command"], channel=matches_tuple["channel"],
				msg=matches_tuple["msg"], tags="color=#B22222;display-name=VolpesBot")
			# this writes to the socket file if the message is valid
			print(message, file=self.handle, flush=True)


	# accepts a channel and a string to send directly as a privmsg
	def send_PRIVMSG(self, channel, text):
		self.token_bucket.get_tokens()
		message = f"PRIVMSG {channel} :{text}"
		self.send_raw(message)


	# special "send_raw" case, this way the console doesnt output the password as plain text
	def send_PASS(self, password):
		self.log("PASS oauth:******************************", nick=self.bot_nick, cmd="PASS", msg="oauth:******************************")
		print("PASS", password, file=self.handle, flush=True)


	# answers to a PING message with a PONG message
	def on_PING(self, data, tags, nick, user, host, cmd, channel, msg):
		self.send_raw(f"PONG :{msg}")
		# self.save_settings()


	# sends a message in the bot own channel every time it joins a channel
	# JOIN is not reliable when connecting to 2+ channels, the server doesnt send JOIN messages for all the channels
	def on_JOIN(self, data, tags, nick, user, host, cmd, channel, msg):
		self.send_PRIVMSG(f"#{self.bot_nick}", f"Joined channel: {channel}")
		pass


	# sends a message in the bot own channel every time it parts a channel
	# PART might not be reliable so dont use it for anything important
	def on_PART(self, data, tags, nick, user, host, cmd, channel, msg):
		self.send_PRIVMSG(f"#{self.bot_nick}", f"Parted channel: {channel}")
		pass


	# answers to a 376 message with a join message
	def on_376(self, data, tags, nick, user, host, cmd, channel, msg):
		self.can_connect = True
		self._join(data, tags, nick, user, host, cmd, channel, msg)


	def on_NOTICE(self, data, tags, nick, user, host, cmd, channel, msg): pass


	def on_PRIVMSG(self, data, tags, nick, user, host, cmd, channel, msg):

		def user_not_authorized():
			self.log(f"User {nick}(owner: {user_is_bot_owner}, broadcaster: {user_is_broadcaster}, "
				f"mod: {user_is_mod}, vip: {user_is_vip}) used command \"{command}\"", cmd="warning")
			self.send_PRIVMSG(channel, "grayfoxWeirdDude you cant use that command")

		# command_ functions are called when the user types a command in chat
		def command_ping():
			uptime = str(datetime.timedelta(seconds = math.floor(time.time() - self.session_variables["startup_time"])))
			self.send_PRIVMSG(channel, f"Uptime: {uptime}")

		def command_redbar():
			if param is None:
				self.send_PRIVMSG(channel, "When the player's Pokémon is at 5/24 or less of their max HP there will be a beeping sound and "
					"you are able to input during Pokémon cries, saving ~1 second every time a Pokémon enters the battle.")
			else:
				try:
					max_hp = int(param.split(maxsplit=1)[0])
					treshold = math.floor(max_hp * 5 / 24)
					self.send_PRIVMSG(channel, f"{treshold}/{max_hp}")
				except ValueError:
					self.send_PRIVMSG(channel, f"Usage: {self.config.get(channel, 'trigger')}{command} max_health")

		def command_gettags():
			if user_is_mod or user_is_broadcaster or user_is_bot_owner:
				self.send_PRIVMSG(channel, data)
			else: user_not_authorized()

		def command_connectedchannels():
			response = "I'm connected to these channels: " + ", ".join(self.session_variables["connected_channels"]) + "."
			self.send_PRIVMSG(channel, response)

		def command_joinchannel():
			if user_is_mod or user_is_broadcaster or user_is_bot_owner:
				newchannel = "#" + param.split()[0].lower()
				if self._join(data, tags, nick, user, host, cmd, channel, msg, newchannel):
					self.send_PRIVMSG(channel, "Joined channel " + newchannel)
				else:
					self.send_PRIVMSG(channel, "Already joined channel " + newchannel)
			else: user_not_authorized()

		def command_partchannel():
			if user_is_mod or user_is_broadcaster or user_is_bot_owner:
				removedchannel = "#" + param.split()[0].lower()
				if removedchannel == "#" + self.bot_nick:
					self.send_PRIVMSG(channel, "I can't leave my own channel, if you don't want me to join this chat on startup edit the settings file")
				elif removedchannel == channel:
					self.send_PRIVMSG(channel, "If you want me to leave this chat use the command in my chat")
				else:
					if self._part(data, tags, nick, user, host, cmd, channel, msg, removedchannel=removedchannel):
						self.send_PRIVMSG(channel, "Left channel " + removedchannel)
					else:
						self.send_PRIVMSG(channel, "I'm not connected to channel " + removedchannel)
			else: user_not_authorized()

		# alias for partchannel
		command_leavechannel = command_partchannel

		def command_banlist():
			if user_is_mod or user_is_broadcaster or user_is_bot_owner:
				try:
					with param.split(maxsplit=3) as params:
						start = int(params_list[0]) if len(params_list) >= 1 else 50
						limit = int(params_list[1]) if len(params_list) >= 2 else 50
						filename = params_list[2] if len(params_list) == 3 else "banlist.txt"
					self.send_PRIVMSG(channel, f"Banning {limit} users starting at line {start} from file {filename}")
				except (AttributeError, ValueError) as error:
					self.log(f"Handled AttributeError or ValueError): {error}")
					self.send_PRIVMSG(channel, f"Usage: {self.config.get(channel, 'trigger')}{command} start amount [filename]")
				else:
					end = start + limit
					try:
						with open(filename, "r", encoding="utf8") as banlist_file:
							banlist = banlist_file.readlines()
						for count in range(start, end):
							banned_user = banlist[count].strip(" \r\n")
							self.send_PRIVMSG(channel, "/ban " + banned_user)
							# time.sleep(0.35)
					except IOError as error:
						self.log(f"Handled IOError: {error}")
						self.send_PRIVMSG(channel, f"Can't find or access file {filename}")
					except IndexError as error:
						self.log(f"Handled IndexError: {error}")
						self.send_PRIVMSG(channel, f"Reached end of {filename}")
				self.send_PRIVMSG(channel, f"Done banning {limit} users starting at line {start} from file {filename}")
			else: user_not_authorized()

		def command_quit():
			if user_is_mod or user_is_broadcaster or user_is_bot_owner:
				self.send_PRIVMSG(channel, "Closing the bot")
				self.ui.quit_var.set()
			else: user_not_authorized()

		def command_restart():
			if user_is_mod or user_is_broadcaster or user_is_bot_owner:
				self.send_PRIVMSG(channel, "Restarting the bot")
				self.ui.restart_var.set()
			else: user_not_authorized()

		# alias for restart
		command_reload = command_restart

		def command_newcommand(): pass

		def command_temptimer():
			if user_is_mod or user_is_broadcaster or user_is_bot_owner:
				threading.Timer(5, self.send_PRIVMSG, args=[channel, "timer ended"]).start()
			else: user_not_authorized()

		def command_error():
			user_not_authorized()


		# create a dictionary for the tags
		tags_dict = {tag.split("=")[0]: tag.split("=")[1] for tag in tags.split(";")}

		# retrieve information about the user
		user_is_bot_owner = True if nick == self.bot_owner else False
		user_is_broadcaster = True if "broadcaster" in tags_dict["badges"] else False
		user_is_mod = True if "moderator" in tags_dict["badges"] else False
		user_is_vip = True if "vip" in tags_dict["badges"] else False

		# check if the bot is setup to delete urls
		if self.config.has_option(channel, "block_urls") and self.config.getboolean(channel, "block_urls") and not (user_is_broadcaster or user_is_mod or user_is_vip):
				if self.regex_url.search(msg) is not None:
					self.send_PRIVMSG(channel, "/delete " + tags_dict["id"])
					self.send_PRIVMSG(channel, "grayfoxWeirdDude no urls")
					self.log(f"Message deleted from user {user}, message content: {msg}", cmd="info")
					return

		# check if the bot is setup to delete messages
		if self.config.has_option(channel, "banned_phrases"):
			# check if a banned string is in the message
			if re.search("(?i)" + self.config.get(channel, "banned_phrases"), msg) is not None and not (user_is_broadcaster or user_is_mod):
				self.send_PRIVMSG(channel, "/delete " + tags_dict["id"])
				self.log(f"Message deleted from user {user}, message content: {msg}", cmd="info")
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
			self.send_PRIVMSG(channel, f"👋 FeelsDankMan hi {tags_dict['display-name']}! I'm a bot.")

		# create the re.match needle to be used in the if statements for the commands
		command_regex = "^" + self.config.get(channel, "trigger") + "(?P<command>\S+)(?:\s+(?P<param>.+?))?\s*$"
		full_command = re.match(command_regex, msg, flags=re.IGNORECASE)

		# commands
		if full_command is not None:
			command = full_command["command"]
			param = full_command["param"]
			try:
				threading.Thread(target=locals()["command_" + command], name=command, daemon=True).start()
			except KeyError as error:
				self.log(f"Handled KeyError: The command {command} doesnt exist")
