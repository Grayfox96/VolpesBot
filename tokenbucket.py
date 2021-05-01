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

# https://dev.twitch.tv/docs/irc/guide

import time

class TokenBucket():

	def __init__(self, bucket_size, time_unit):
		self.bucket_size = bucket_size
		self.tokens = 0
		self.time_unit = time_unit
		self.filling_rate = bucket_size / time_unit
		self.last_fill = time.time()

	def get_tokens(self, tokens=1):

		# setup time variables
		time_now = time.time()
		time_elapsed = time_now - self.last_fill
		self.last_fill = time_now

		#fill the bucket
		self.tokens = self.tokens + (time_elapsed * self.filling_rate)

		# discard overflowing tokens
		if self.tokens > self.bucket_size:
			self.tokens = self.bucket_size

		# either remove tokens from the bucket or wait for the appropriate amount of time
		if self.tokens >= tokens:
			self.tokens -= tokens
		else:
			time.sleep(tokens / self.filling_rate)
			self.log(f"Hit rate limit, {self.tokens} tokens left after refilling.")