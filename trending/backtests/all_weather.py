import calendar
import datetime

from trending import settings
from trending.strategy.base import AbstractStrategy
from trending.position_sizer.rebalance import LiquidateRebalancePositionSizer
from trending.event import SignalEvent, EventType
import queue
from trending.trading_session import TradingSession


class MonthlyLiquidateRebalanceStrategy(AbstractStrategy):
	"""
    A generic strategy that allows monthly rebalancing of a
    set of tickers, via full liquidation and dollar-weighting
    of new positions.
    Must be used in conjunction with the
    LiquidateRebalancePositionSizer object to work correctly.
    """

	def __init__(self, tickers, events_queue):
		self.tickers = tickers
		self.events_queue = events_queue
		self.tickers_invested = self._create_invested_list()


	def _end_of_quarter(self, cur_time):
		"""
		Determine is current day is at the end of the quarter
		"""

		cur_month = cur_time.month
		quarter_months = [3, 6, 9, 12]

		cur_day = cur_time.day
		end_day = calendar.monthrange(cur_time.year, cur_time.month)[1]
		return cur_day == end_day and cur_month in quarter_months

	def _end_of_month(self, cur_time):
		"""
        Determine if the current day is at the end of the month.
        """
		cur_day = cur_time.day
		end_day = calendar.monthrange(cur_time.year, cur_time.month)[1]
		return cur_day == end_day

	def _end_of_year(self, cur_time):
		"""
		determine if current day is end of the year
		"""
		cur_month = cur_time.month
		cur_day = cur_time.day
		end_day = calendar.monthrange(cur_time.year, cur_time.month)[1]

		return cur_day == end_day and cur_month == 12


	def _create_invested_list(self):
		"""
        Create a dictionary with each ticker as a key, with
        a boolean value depending upon whether the ticker has
        been "invested" yet. This is necessary to avoid sending
        a liquidation signal on the first allocation.
        """
		tickers_invested = {ticker:False for ticker in self.tickers}
		return tickers_invested

	def calculate_signals(self, event):
		"""
        For a particular received BarEvent, determine whether
        it is the end of the month (for that bar)/ quarter / year and generate
        a liquidation signal, as well as a purchase signal,
        for each ticker.
        """
		if (
				event.type in [EventType.BAR, EventType.TICK] and
				self._end_of_quarter(event.time)
		):
			ticker = event.ticker
			if self.tickers_invested[ticker]:
				liquidate_signal = SignalEvent(ticker, "EXIT")
				self.events_queue.put(liquidate_signal)
			long_signal = SignalEvent(ticker, "BOT")
			self.events_queue.put(long_signal)
			self.tickers_invested[ticker] = True


def run(config, testing, tickers, filename):
	"""
	http://www.lazyportfolioetf.com/allocation/ray-dalio-all-weather/

	All weather portfolio,
	We show the regular weightings
	And use 2x leveraged ETFs to show the leveraged version. 
	"""


	# Backtest information
	title = [
		'quarterly Liquidate/Rebalance on All-Weather\n30%/15%/40%/7.5%/7.5% SPY/IEF/TLT/GLD/DBC Portfolio'
	]
	# title = [
	# 	'Monthly Liquidate/Rebalance on All-Weather2x\n30%/15%/40%/7.5%/7.5% FLGE/UST/UBT/DGP/DBC Portfolio'
	# ]
	initial_equity = 100000.0
	start_date = datetime.datetime(2011, 1, 1)
	end_date = datetime.datetime(2020, 6, 5)

	# Use the Monthly Liquidate And Rebalance strategy
	events_queue = queue.Queue()
	strategy = MonthlyLiquidateRebalanceStrategy(
		tickers, events_queue
	)

	# Use the liquidate and rebalance position sizer
	# with prespecified ticker weights
	ticker_weights = {
		"SPY": 0.3,
		"IEF": 0.15,
		"TLT": 0.4,
		"GLD": 0.075,
		"DBC": 0.075
	}

	# ticker_weights = {
	# 	"SSO":0.29,
	# 	"FLGE": 0.29,
	# 	"UST": 0.15,
	# 	"UBT": 0.4,
	# 	"DGP": 0.075,
	# 	"DBC": 0.075,
	# 	"SPY": 0.01
	# }

	position_sizer = LiquidateRebalancePositionSizer(
		ticker_weights
	)

	# Set up the backtest
	backtest = TradingSession(
		config, strategy, tickers,
		initial_equity, start_date, end_date,
		events_queue, position_sizer=position_sizer,
		adjusted_or_close='adj_close',
		title=title, benchmark=tickers[0],
	)
	results = backtest.start_trading(testing=testing, filename=filename)
	return results


if __name__ == "__main__":
	# Configuration data
	testing = False
	config = settings.from_file(
		settings.DEFAULT_CONFIG_FILENAME, testing
	)
	tickers = ["SPY", "IEF", "TLT", "GLD", "DBC"]
	# tickers = ["FLGE", "UST", "UBT", "DGP", "DBC", "SPY"]
	filename = "/home/joe/Desktop/all_weather_1x.png"
	run(config, testing, tickers, filename)

