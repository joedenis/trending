# TODO currently we are trading on the same day that the indicators are calculated! Could move this to trade the nxt day


import datetime
import calendar
import pandas_market_calendars as mcal
import numpy as np

import pandas as pd

from trending import settings

from trending.strategy.base import AbstractStrategy
from trending.event import SignalEvent, EventType

from trending.position_sizer.risk_parity_atr import RiskParityATRPositionSizer

from trending.price_parser import PriceParser

# from trending.risk_manager.example import ExampleRiskManager
from trending.risk_manager.expo_momo_risk_manager import ExpoMomoRiskManager
from trending.portfolio_handler import PortfolioHandler
from trending.price_handler.yahoo_daily_csv_bar import YahooDailyCsvBarPriceHandler

import queue
from collections import deque
import itertools

from trending.trading_session import TradingSession
from scipy.stats import linregress


class ExponentialMomentum(AbstractStrategy):
	"""
	Uses an exponential momentum * r^2 to rank assets, 90 days default.
	Invests in the highest ranking assets if the index is above the 200dma and the asset is above 100DMA and no
	large gap of 15% in last 100 days.
	stocks are sold if they move out of the ranking or if below the 100DMA or if it moved over 15%

	positions are adjusted for risk using atr (average true range) 20 day
	"""

	def __init__(
			self, tickers, events_queue, calendars, first_date_dict,
			window=90, atr_period=20, index_filter="SPY"
	):
		self.tickers = tickers
		self.index_ticker = index_filter
		self.events_queue = events_queue
		"""
		keep track of the prices we have seen for a given day
		"""

		self.first_date_dict = first_date_dict

		self.time = None
		self.latest_prices = np.full(len(self.tickers), -1.0)

		# index 200dma calculation:
		self.index_dma_window = 200
		self.index_prices = deque(maxlen=self.index_dma_window)
		self.index_dma = False

		self.tickers_invested = self._create_invested_list()

		# counting bars not needed for monthyl trading
		self.bars = 0

		self.calendars = calendars
		self.window = window
		self.sma_days_for_stocks = 100

		self.atr_period = atr_period

		# creating the queues for each asset in tickers list
		#  queue for closing prices adjusted
		self.ticker_bars = {}
		# queue for unadjusted prices
		self.ticker_bars_unadj = {}
		# queue for storing true range
		self.true_range = {}
		# dictionary to calculate the true range
		self.high_lows = {}
		# dictionary to store pd Series of average true range
		self.atr = {}

		for ticker in tickers:
			self.ticker_bars[ticker] = deque(maxlen=self.sma_days_for_stocks)
			self.ticker_bars_unadj[ticker] = deque(maxlen=self.sma_days_for_stocks)
			self.high_lows[ticker] = dict.fromkeys(['today_high', 'today_low', 'yes_close'])
			self.true_range[ticker] = deque(maxlen=100)
			# average true range will be stored here when we have a series
			self.atr[ticker] = None

	def _set_correct_time_and_price(self, event):
		"""
		Sets the correct price and event time for prices
		that arrive out of order in the events queue.
		"""
		# Set the first instance of time
		if self.time is None:
			self.time = event.time

		# Set the correct latest prices depending upon
		# order of arrival of market bar event
		price = event.adj_close_price / PriceParser.PRICE_MULTIPLIER
		if event.time == self.time:
			index = self.tickers.index(event.ticker)
			self.latest_prices[index] = price

			# if event.ticker == self.tickers[0]:
			#     self.latest_prices[0] = price
			# else:
			#     self.latest_prices[1] = price
		else:
			self.time = event.time
			# self.days += 1
			self.latest_prices = np.full(len(self.tickers), -1.0)
			index = self.tickers.index(event.ticker)
			self.latest_prices[index] = price

			# if event.ticker == self.tickers[0]:
			#     self.latest_prices[0] = price
			# else:
			#     self.latest_prices[1] = price

	def number_of_valid_ticks_on_day(self, today):
		count = 0
		for ticker in self.first_date_dict:
			if today >= self.first_date_dict[ticker]:
				count += 1
		return count

	def valid_tickers(self, today):
		lister = []
		for ticker in self.first_date_dict:
			if today >= self.first_date_dict[ticker]:
				lister.append(ticker)

		return lister

	def _end_of_month(self, cur_time):
		"""
		Determine if the current day is at the end of the month.
		"""
		cur_day = cur_time.day
		end_day = calendar.monthrange(cur_time.year, cur_time.month)[1]
		return cur_day == end_day

	def _end_of_month_business(self, cur_time):
		year = cur_time.year
		string = '1/1/' + str(year)
		days = pd.date_range(string, periods=12, freq='BM')

		return cur_time in set(days)

	def _end_of_month_trading_calendar(self, cur_time):
		"""
		Return if the current day is end of month in the given exchange (LSE)
		"""
		year = cur_time.year
		daily = self.calendars[year]

		month1 = pd.Series(daily.month)
		month2 = pd.Series(daily.month).shift(-1)
		mask = (month1 != month2)

		month_ends = daily[mask.values]
		month_ends = month_ends.floor('d')

		cur_date_string = cur_time.strftime('%Y-%m-%d')

		listy = month_ends.strftime('%Y-%m-%d')
		return cur_date_string in set(listy)

	def _end_of_quarter(self, cur_time):
		"""
		Determine is current day is at the end of the quarter
		"""
		cur_month = cur_time.month
		quarter_months = [3, 6, 9, 12]

		cur_day = cur_time.day
		end_day = calendar.monthrange(cur_time.year, cur_time.month)
		# [1]
		return cur_day == end_day and cur_month in quarter_months

	def is_second_wed(self, date):
		"""
		used for the event date being the second wednesday of the month
		:param date: datetime event.time
		:return: bool
		"""
		return date.weekday() == 2 and 8 <= date.day <= 14

	def _create_invested_list(self):
		"""
			Create a dictionary with each ticker as a key, with
			a boolean value depending upon whether the ticker has
			been "invested" yet. This is necessary to avoid sending
			a liquidation signal on the first allocation.
		"""
		tickers_invested = {ticker: False for ticker in self.tickers}
		return tickers_invested

	def expo_momentum(self, prices):
		"""
		:param prices: closing prices of the asset
		:return: the slope coefficient from a regression multiply by R^2 (regression coef)
		"""
		returns = np.log(prices)
		x = np.arange(len(returns))
		slope, _, rvalue, _, _ = linregress(x, returns)
		return ((1 + slope) ** 252) * (rvalue ** 2)  # annualize slope and multiply by R^2

	def below_100_dma(self, price, ticker):
		"""
		used for exiting risky assets
		returns whether the asset is below the 100dma
		:param price: current price of the asset from the event.
		:param ticker:
		:return: bool
		"""
		all_days = list(itertools.islice(self.ticker_bars[ticker], 0, len(self.ticker_bars[ticker])))
		all_days = np.asarray(all_days, dtype=np.float32)

		hundred_day_sma = np.mean(all_days)

		if price < hundred_day_sma:
			return True
		else:
			return False

	def move_greater_than_15(self, ticker):
		"""
		used to exit risky assets
		returns whether there has been a move greater than 15% in the last 100 bars
		:param ticker:
		:return:
		"""
		all_days = list(itertools.islice(self.ticker_bars[ticker], 0, len(self.ticker_bars[ticker])))
		all_days = np.asarray(all_days, dtype=np.float32)

		percentage_moves = np.diff(all_days) / all_days[:-1] * 100
		percentage_moves = abs(percentage_moves)
		max_move = np.max(percentage_moves)

		if max_move > 15.0:
			return True
		else:
			return False

	def calculate_signals(self, event):
		if (
				event.type in [EventType.BAR, EventType.TICK] and
				event.ticker in self.tickers
				# and self._end_of_month_trading_calendar(event.time)
		):
			self.bars += 1
			self._set_correct_time_and_price(event)

			#  IF IT IS THE INDEX, THEN WE ONLY USE TO CALCULATE THE 200DAY MOVING AVERAGE
			if event.ticker == self.index_ticker:
				self.index_prices.append(event.adj_close_price)
				if len(self.index_prices) == self.index_dma_window:
					# close = self.index_prices[-1]
					# are_we_above = self.index_prices[-1] > np.mean(self.index_prices)
					self.index_dma = self.index_prices[-1] > np.mean(self.index_prices)

			# ticker = event.ticker
			# add closing prices to prices queue
			self.ticker_bars[event.ticker].append(event.adj_close_price)
			self.ticker_bars_unadj[event.ticker].append(event.close_price)

			# add todays prices prices and yesterdays prices
			# first we move the old price
			# self.high_lows[event.ticker]['yes_high'] = self.high_lows[event.ticker]['today_high']
			# self.high_lows[event.ticker]['yes_close'] = self.high_lows[event.ticker]['today_low']
			# today_high = event.high_price
			# today_high =

			self.high_lows[event.ticker]['today_high'] = int(
				event.high_price * event.adj_close_price / event.close_price)
			self.high_lows[event.ticker]['today_low'] = int(event.low_price * event.adj_close_price / event.close_price)

			todays_high = self.high_lows[event.ticker]['today_high']
			todays_low = self.high_lows[event.ticker]['today_low']

			if len(self.ticker_bars_unadj[event.ticker]) > 1:
				yesterdays_close = self.ticker_bars[event.ticker][-2]

				true_range = np.max([todays_high, yesterdays_close]) - np.min([todays_low, yesterdays_close])
				self.true_range[event.ticker].append(true_range)

				if len(self.true_range[event.ticker]) >= 20:
					queue_of_tr = pd.Series(self.true_range[event.ticker])
					atr_series = queue_of_tr.ewm(span=20, min_periods=self.atr_period).mean()
					self.atr[event.ticker] = atr_series

			# can only trade if all tickers have more than 90 days
			enough_days = True

			valid_tickers_for_day = self.valid_tickers(self.time)

			for ticker in valid_tickers_for_day:
				if len(self.ticker_bars[ticker]) < self.window or len(
						self.ticker_bars[ticker]) < self.sma_days_for_stocks:
					enough_days = False
					if not enough_days:
						break

			if enough_days:
				number_of_stocks_prices_seen = np.sum(self.latest_prices > -1.0)
				threshold = self.number_of_valid_ticks_on_day(self.time)

			if enough_days and event.time.weekday() == 2 and number_of_stocks_prices_seen >= threshold:
				"""calculate momentums"""

				# momentums = pd.DataFrame(self.tickers)
				momenta = {}
				for ticker in valid_tickers_for_day:
					# closing_prices = list(self.ticker_bars[ticker])
					closing_prices = list(
						itertools.islice(self.ticker_bars[ticker], self.sma_days_for_stocks - self.window,
										 self.sma_days_for_stocks))
					momenta[ticker] = self.expo_momentum(closing_prices)

				# momenta_df = pd.DataFrame(list(momenta.items), columns=['Asset', 'Momentum'])
				# momenta_df = momenta_df.sort_values(by = 'Momentum')

				# remove the index ticker from the table as we won't buy that
				momenta.pop(self.index_ticker, None)

				# interested in top half best performing assets
				n = int((len(valid_tickers_for_day) - 1) / 2)

				top_n = {key: momenta[key] for key in sorted(momenta, key=momenta.get, reverse=True)[:n]}

				top_assets = list(top_n.keys())

				"""
				Do any stocks we own need to be sold?
				"""
				for stock in self.tickers_invested:
					if self.tickers_invested[stock]:
						"""
						check if we need to sell this
						"""
						"""
						if stock not in top assets ---> SELL
						if stock is below 100DMA --> SELL
						if gap over 15% --> SELL
						
						we need to update the tables every wednesday.  Either we keep the table as part of a class.
						Or for every tick coming in we calculate and then trade.
						
						"""
						if stock not in top_assets:
							liquidate_signal = SignalEvent(stock, "EXIT")
							self.events_queue.put(liquidate_signal)
							self.tickers_invested[stock] = False
						elif self.below_100_dma(self.ticker_bars[stock][-1], stock):
							liquidate_signal = SignalEvent(stock, "EXIT")
							self.events_queue.put(liquidate_signal)
							self.tickers_invested[stock] = False
						elif self.move_greater_than_15(stock):
							liquidate_signal = SignalEvent(stock, "EXIT")
							self.events_queue.put(liquidate_signal)
							self.tickers_invested[stock] = False

				"""
				can we buy any stocks
				only if the index is above the 200DMA
				and if the stock is above 100DMA 
				and no move larger than 15%
				go through the top momentum list.  if we do not own buy until we run out of cash                
				"""
				if self.index_dma:
					for ticker in top_assets:
						if not self.below_100_dma(self.ticker_bars[ticker][-1], ticker) \
								and not self.move_greater_than_15(ticker):

							if self.tickers_invested[ticker]:
								pass
							else:
								size = int(self.atr[ticker].iloc[-1])

								long_signal = SignalEvent(ticker, "BOT", size)
								self.events_queue.put(long_signal)

								self.tickers_invested[ticker] = True
				"""
				rebalance if its a second wednesday 
				what is the target size and what is the currents size of the position.
				if the difference is too much rebalance 
				
				go through all the assets with booleans. And then place orders to buy.  The position sizer will see its a rebalance
				then          
				"""
				if self.is_second_wed(event.time):
					for stock in self.tickers_invested:
						if self.tickers_invested[stock]:
							size = int(self.atr[stock].iloc[-1])

							long_signal = SignalEvent(stock, "BOT", size)
							self.events_queue.put(long_signal)


def get_yearly_trading_calendar(year, cal='LSE'):
	"""
	Used to get the trading days using the LSE calendar
	uses pandas-market-calendars
	'NYSE', 'LSE', 'CME', 'EUREX', 'TSX'
	"""
	lse = mcal.get_calendar(cal)
	year = lse.schedule(start_date=str(year) + '-01-01', end_date=str(year) + '-12-31')
	daily = mcal.date_range(year, frequency='1D')

	return daily


def get_dict_of_trading_calendars(years, cal='LSE'):
	"""
	:param cal: calendar eg LSE, NYSE, EUREX
	:param years: a list of years
	:return: tradng calendars dictionary with years as the keys
	Pass this to the backtester
	"""
	cal_dict = {}
	for year in years:
		cal_dict[year] = get_yearly_trading_calendar(year, cal)

	return cal_dict


def run(config, testing, tickers, _filename, initial_equity):
	# Backtest information
	title = ['Exponential momentum on basket %s' % tickers]

	year_start = 2000
	year_end = 2019

	start_date = datetime.datetime(year_start, 12, 28)

	todays_month = int(datetime.datetime.today().strftime("%m"))
	todays_day = int(datetime.datetime.today().strftime("%d"))
	end_date = datetime.datetime(year_end, todays_month, todays_day)

	csv_dir = config.CSV_DATA_DIR
	adjusted_or_close = 'adj_close'

	events_queue = queue.Queue()

	price_handler = YahooDailyCsvBarPriceHandler(
		csv_dir, events_queue, tickers,
		start_date=start_date, end_date=end_date,
		calc_adj_returns=True
	)

	"""
	we need to pass the first date dictionary ino the strategy,  the np of -1s needs t obe the length 
	on a given day how many -1s are we expecting.
	
	"""
	first_date_dict = {}
	for ticker in price_handler.tickers:
		first_date_dict[ticker] = price_handler.tickers[ticker]['timestamp']

	years = list(range(year_start, year_end + 1))
	calendars = get_dict_of_trading_calendars(years, cal='LSE')

	# Use the Buy and Hold Strategy
	strategy = ExponentialMomentum(tickers, events_queue, calendars, first_date_dict)

	risk_per_stock = 0.012

	ticker_weights = {}
	for ticker in tickers:
		ticker_weights[ticker] = risk_per_stock

	# ticker_weights = {
	#     "BP.L": 1,
	#     "GSK.L": 1,
	#     "ITV.L": 1,
	#     "NG.L": 1
	# }

	position_sizer = RiskParityATRPositionSizer(
		ticker_weights
	)

	# risk_manager = ExampleRiskManager()
	risk_manager = ExpoMomoRiskManager(PriceParser.parse(initial_equity))

	portfolio_handler = PortfolioHandler(
		PriceParser.parse(initial_equity),
		events_queue,
		price_handler,
		position_sizer,
		risk_manager,
		adjusted_or_close
	)

	# Set up the backtest
	backtest = TradingSession(
		config, strategy, tickers,
		initial_equity, start_date, end_date,
		events_queue, title=title,
		adjusted_or_close=adjusted_or_close,
		position_sizer=position_sizer,
		portfolio_handler=portfolio_handler,
		price_handler=price_handler
	)

	results = backtest.start_trading(testing=testing, filename=_filename)
	return results


if __name__ == "__main__":
	# Configuration data
	testing = False
	config = settings.from_file(
		settings.DEFAULT_CONFIG_FILENAME, testing
	)
	tickers = ["BP.L", "GSK.L", "ITV.L", "NG.L", "TSLA", "FB", "AMZN", "AAPL", "SPY"]

	filename = "/home/joe/Desktop/expo_momo.png"
	initial_equity = 100000.0
	run(config, testing, tickers, filename, initial_equity)
