"""
The accelerated momentume strategy has a portfolio that only buys
US market, International Equities, or Long Term Government bonds

We calculate the 1 month 3 month and 6 month returns for the two Equity Indices

We score each index by averaging the 3 returns.

If both scores are negative it indicates that the markets are trending down so we buy bonds

Otherwise we invest 100% of the portfolio into the best performing Index.

We rebalance our holdings monthly.
"""
from collections import deque
import calendar
import datetime

import numpy as np
import pandas as pd

from trending import settings

from trending.strategy.base import AbstractStrategy
from trending.event import SignalEvent, EventType

import queue

from trending.trading_session import TradingSession

'''NEED TO ADD THAT WE ONLY TRADE MONTHLY...'''

class AcceleratingMomentumStrategy(AbstractStrategy):
	"""
	tickers :  We use the 3 tickers!
	events_queue: feeding to the system events queue

	where do we store the 1 month 3 month and 6 month returns.
	we only need 3 bytes to store this and another to calculate the results

	I suppose we first write this for just 1 ticker!!!

	"""

	def __init__(
			self, tickers, safe_asset,
			events_queue,
			trade_freq = 21, # we will trade every month
			first_window = 21,  # 1month, 3month and 6month returns in business days
			second_window = 63,
			third_window = 126,
			base_quantity = 100  #needed for how much we invest in the portfolio
	):
		self.tickers = tickers
		self.safe_asset = safe_asset
		self.asset_to_invest_in = None
		self.events_queue = events_queue
		self.trade_freq = trade_freq
		self.first_window = first_window
		self.second_window = second_window
		self.third_window = third_window
		self.base_quantity = base_quantity
		self.bars = 0
		self.tickers_invested = self._create_invested_list()
		self.prices_df = pd.DataFrame(columns=[tickers], dtype=int)
		# creating the queue for each asset in tickers list
		self.ticker_bars = {}
		for ticker in tickers:
			self.ticker_bars[ticker] = deque(maxlen=self.third_window)


		# we use a series as we only have one ticker coming in here
		# self.prices_df = pd.Series([])
	def _end_of_month(self, cur_time):
		"""
		Determine if the current day is at the end of the month.
		"""
		cur_day = cur_time.day
		end_day = calendar.monthrange(cur_time.year, cur_time.month)[1]
		return cur_day == end_day

	def _create_invested_list(self):
		"""
			Create a dictionary with each ticker as a key, with
			a boolean value depending upon whether the ticker has
			been "invested" yet. This is necessary to avoid sending
			a liquidation signal on the first allocation.
		"""
		tickers_invested = {ticker:False for ticker in self.tickers}
		return tickers_invested

	def which_asset_to_invest(self, rank_assets, water_mark=0):
		# water_mark = 0
		current_high = 0
		best_performer = None

		for asset in rank_assets:
			if rank_assets[asset] <= water_mark:
				return self.safe_asset
			elif rank_assets[asset] > current_high:
				current_high = rank_assets[asset]
				best_performer = asset

		return best_performer
	# Next up we have to write how to calculate the signals for all three
	# we start by an allocation to one asset.

	def calculate_signals(self, event):
		if (
			event.type in [EventType.BAR, EventType.TICK] and
			event.ticker in self.tickers
		):
			no_invested = 0
			for key in self.tickers_invested:
				if self.tickers_invested[key]:
					no_invested += 1
			if no_invested > 1:
				print("**************")
				print("INVESTED IN", no_invested, "ASSETS")
				print("**************")
			elif no_invested == 0 and self.bars > self.third_window:
				print("**************")
				print("EMPTY PORTFOLIO")
				print("**************")
			# if self.tickers_invested

			for key in self.tickers_invested:
				if key != self.asset_to_invest_in and self.tickers_invested[key] == True:
					print("We should not be invested EXITING", key, "NOT equal to", self.asset_to_invest_in)
					print("EXIT %s: %s" % (event.ticker, event.time))
					liquidate_signal = SignalEvent(event.ticker, "EXIT")
					self.events_queue.put(liquidate_signal)
					self.tickers_invested[event.ticker] = False

			# append the price to the queue
			self.ticker_bars[event.ticker].append(event.adj_close_price)

			# this assumes an equal amount of bars in each input
			# if self.bars > (len(self.tickers) * self.third_window) + 1:
			can_trade = True
			for ticker in self.ticker_bars:
				if len(self.ticker_bars[ticker]) < self.third_window:
					can_trade = False
			# now we have six months of prices in our bars
			# we create a dictionary with the mean returns over lookback periods
			#
			if can_trade:
				rank_assets = {}
				# risky_assets =
				for ticker in self.tickers:
					if ticker != self.safe_asset:
						current_price = self.ticker_bars[ticker][-1]
						one_month = (current_price - self.ticker_bars[ticker][-1 - self.first_window] ) / current_price
						three__month = (current_price - self.ticker_bars[ticker][-1 - self.second_window]) / current_price
						six_month = (current_price - self.ticker_bars[ticker][-1 - self.third_window + 1]) / current_price

						accel_momo = np.mean([one_month, three__month, six_month])
						rank_assets[ticker] = accel_momo

				# NOW WE KNOW WHICH ASSET TO BUY DO WE BUY IT ON THE NEXT DAY??
				asset_to_trade = self.which_asset_to_invest(rank_assets)


				# action at end of the month
				if self._end_of_month(event.time):
					print(asset_to_trade, "IS THE ASSET TO OWN", event.time)
					self.asset_to_invest_in = asset_to_trade
					ticker = event.ticker
					# and we are not invested
					if ticker == asset_to_trade and not self.tickers_invested[ticker]:
						print("LONG %s: %s" % (ticker, event.time))
						long_signal = SignalEvent(ticker, "BOT", suggested_quantity=self.base_quantity)
						self.events_queue.put(long_signal)
						self.tickers_invested[ticker] = True
					elif ticker != asset_to_trade and self.tickers_invested[ticker]:
						print("EXIT %s: %s" % (ticker, event.time))
						liquidate_signal = SignalEvent(ticker, "EXIT")
						self.events_queue.put(liquidate_signal)
						self.tickers_invested[ticker] = False
			self.bars += 1

			"""
			ABOVE WE NEED to buy the asset.  Check if we are already in the asset.  If we are do nothing.
			If we are not. Liquidate portfolio and buy the asset.
			"""



def run(config, testing, tickers, safe_asset, filename):
	# Backtest information
	title = ['Accelerating momentum for SPX, BONDS, MSCI: 1m, 3m, 6m > 0']
	initial_equity = 10000.0
	start_date = datetime.datetime(2000, 1, 1)
	end_date = datetime.datetime(2014, 1, 1)

	# Use the MAC Strategy
	events_queue = queue.Queue()
	strategy = AcceleratingMomentumStrategy(
		tickers, safe_asset, events_queue
	)

	# Set up the backtest
	backtest = TradingSession(
		config, strategy, tickers,
		initial_equity, start_date, end_date,
		events_queue, title=title,
		benchmark=tickers[1],
	)
	results = backtest.start_trading(testing=testing)
	# results = backtest.start_trading(testing=Fa)

	return results


if __name__ == "__main__":
	# Configuration data
	testing = False

	# unresolved referenece for settings
	config = settings.from_file(
		settings.DEFAULT_CONFIG_FILENAME, testing
	)
	tickers = ["VUSTX", "SPY", "VINEX"]
	safe_asset = "VUSTX"
	filename = None

	spy_momo = run(config, testing, tickers, safe_asset, filename)

	print(spy_momo['positions'])


