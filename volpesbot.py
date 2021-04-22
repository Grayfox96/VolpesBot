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

from volpesbot_irc import *


irc_bot = irc_bot()

irc_bot.connect()

# iterate all the lines in the buffer
for line in irc_bot.handle:

	# remove spaces from the end of the string
	line = line.strip()

	# divide all the data into appropriate variables
	matches_tuple = irc_bot.regex_message.match(line)
	data = line
	tags = matches_tuple["tags"]
	nick = matches_tuple["nick"]
	user = matches_tuple["user"]
	host = matches_tuple["host"]
	cmd = matches_tuple["cmd"]
	channel = matches_tuple["channel"]
	msg = matches_tuple["msg"]

	# log data received
	irc_bot.log(data, tags, nick, user, host, cmd, channel, msg)

	# call the appropriate function if it exists
	if hasattr(irc_bot, "on_" + cmd):
		getattr(irc_bot, "on_" + cmd)(data, tags, nick, user, host, cmd, channel, msg)

	# if the program has been flagged to be closed
	if irc_bot.ui.quit_var.get():
		print("Closing script")
		# save the settings in the settings file
		irc_bot.save_settings()
		# close the ui (its running in different thread)
		irc_bot.ui.root.quit()
		# close the program
		quit()
