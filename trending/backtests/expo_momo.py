import datetime
import calendar
import pandas_market_calendars as mcal
import numpy as np

import pandas as pd

from trending import settings

from trending.strategy.base import AbstractStrategy
from trending.event import SignalEvent, EventType
from trending.position_sizer.rebalance import LiquidateRebalancePositionSizer

import queue
from collections import deque

from trending.trading_session import TradingSession
from scipy.stats import linregress

class ExponentialMomentum(AbstractStrategy):
    """
    A testing strategy that simply purchases (longs) an asset
    upon first receipt of the relevant bar event and
    then holds until the completion of a backtest.

    We use a monthly rebalance.
    We give it calendars to only trade when markets are open
    """
    def __init__(
        self, tickers, events_queue, calendars,
            window = 90, atr_period=20
        # base_quantity=100
    ):
        self.tickers = tickers
        self.events_queue = events_queue
        # self.base_quantity = base_quantity
        # counting bars not needed for monthyl trading
        self.bars = 0
        self.invested = False
        self.calendars = calendars
        self.window = window
        self.atr_period = atr_period

        self.tickers_invested = self._create_invested_list()

        # creating the queues for each asset in tickers list
        #  queue for closing prices
        self.ticker_bars = {}
        # queue for storing true range
        self.true_range = {}
        # dictionary to calculate the true range
        self.high_lows = {}
        # dictionary to store pd Series of average true range
        self.atr = {}

        for ticker in tickers:
            self.ticker_bars[ticker] = deque(maxlen=self.window)
            self.high_lows[ticker] = dict.fromkeys(['today_high', 'today_low', 'yes_close'])
            self.true_range[ticker] = deque(maxlen=100)
            # average true range will be stored here when we have a series
            self.atr[ticker] = None

    #     creating high lows for asset calculations
    #     self.high_lows = {}
    #     for ticker in tickers:
    #         self.high_lows[ticker] = dict.fromkeys(['today_high', 'today_low', 'yes_close'])

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

    def _create_invested_list(self):
        """
			Create a dictionary with each ticker as a key, with
			a boolean value depending upon whether the ticker has
			been "invested" yet. This is necessary to avoid sending
			a liquidation signal on the first allocation.
		"""
        tickers_invested = {ticker:False for ticker in self.tickers}
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





    def calculate_signals(self, event):
        if (
            event.type in [EventType.BAR, EventType.TICK] and
            event.ticker in self.tickers
                # and self._end_of_month_trading_calendar(event.time)
        ):
            ticker = event.ticker
            # add closing prices to prices queue
            self.ticker_bars[event.ticker].append(event.adj_close_price)

            # add todays prices prices and yesterdays prices
            # first we move the old price
            # self.high_lows[event.ticker]['yes_high'] = self.high_lows[event.ticker]['today_high']
            # self.high_lows[event.ticker]['yes_close'] = self.high_lows[event.ticker]['today_low']
            self.high_lows[event.ticker]['today_high'] = event.high_price
            self.high_lows[event.ticker]['today_low'] = event.low_price

            todays_high = self.high_lows[event.ticker]['today_high']
            todays_low = self.high_lows[event.ticker]['today_low']

            if len(self.ticker_bars[event.ticker]) > 1:
                yesterdays_close = self.ticker_bars[event.ticker][-2]

                true_range = np.max([todays_high, yesterdays_close]) - np.min([todays_low, yesterdays_close])
                self.true_range[event.ticker].append(true_range)

                if len(self.true_range[event.ticker]) >= 20:
                    queue_of_tr = pd.Series(self.true_range[event.ticker])
                    atr_series = queue_of_tr.ewm(span=20, min_periods=self.atr_period).mean()
                    self.atr[ticker] = atr_series

            #         TODO we have the average true range working for a default of 20 days. This value is a large integer to avoid precision
            # TODO translate the ATR into a portfolio weighting!
            #




            # can only trade if all tickers have more than 90 days
            can_trade = True
            for ticker in self.ticker_bars:
                if len(self.ticker_bars[ticker]) < self.window:
                    can_trade = False
                    if not can_trade:
                        break

            if can_trade and self._end_of_month_trading_calendar(event.time):

                """
                TODO if we can trade how to make sure we invest in the right tickers when the 
                event system is created
                
                we know which assets we should be in.  So we need to control the liquidate and invest
                signals.  Look out for not liquidating the first buys of the portfolio.
                
                look at our example in momo_two_stocks
                
                how do we timestamp individual assets coming through. guess once we have seen all the assets for a given day
                calculate the indicator on that day.  Signal goes out to buy or sell for the next day.
                
                
                """
                # momentums = pd.DataFrame(self.tickers)
                momenta = {}
                for ticker in self.tickers:
                    closing_prices = list(self.ticker_bars[ticker])
                    momenta[ticker] = self.expo_momentum(closing_prices)

                # momenta_df = pd.DataFrame(list(momenta.items), columns=['Asset', 'Momentum'])
                # momenta_df = momenta_df.sort_values(by = 'Momentum')
                n = 2
                top_n = {key:momenta[key] for key in sorted(momenta, key=momenta.get, reverse=True)[:n]}

                top_assets = list(top_n.keys())

                print(top_assets)





                if self.invested:
                    liquidate_signal = SignalEvent(ticker, "EXIT")
                    self.events_queue.put(liquidate_signal)
                long_signal = SignalEvent(ticker, "BOT")
                self.events_queue.put(long_signal)

                self.invested = True


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

    year_start = 2016
    year_end = 2019

    start_date = datetime.datetime(year_start, 12, 28)

    todays_month = int(datetime.datetime.today().strftime("%m"))
    todays_day = int(datetime.datetime.today().strftime("%d"))
    end_date = datetime.datetime(year_end, todays_month, todays_day)

    years = list(range(year_start, year_end + 1))
    calendars = get_dict_of_trading_calendars(years, cal='LSE')

    # Use the Buy and Hold Strategy
    events_queue = queue.Queue()
    strategy = ExponentialMomentum(tickers, events_queue, calendars)


    allocation = 1 / len(tickers)
    ticker_weights = {}
    for ticker in tickers:
        ticker_weights[ticker] = allocation

    # ticker_weights = {
    #     "BP.L": 1,
    #     "GSK.L": 1,
    #     "ITV.L": 1,
    #     "NG.L": 1
    # }

    position_sizer = LiquidateRebalancePositionSizer(
        ticker_weights
    )

    # Set up the backtest
    backtest = TradingSession(
        config, strategy, tickers,
        initial_equity, start_date, end_date,
        events_queue, title=title,
        adjusted_or_close='adj_close',
        position_sizer=position_sizer
    )

    results = backtest.start_trading(testing=testing, filename=_filename)
    return results


if __name__ == "__main__":
    # Configuration data
    testing = False
    config = settings.from_file(
        settings.DEFAULT_CONFIG_FILENAME, testing
    )
    tickers = ["BP.L", "GSK.L", "ITV.L", "NG.L"]
    filename = "/home/joe/Desktop/expo_momo.png"
    initial_equity = 22500000.0
    run(config, testing, tickers, filename, initial_equity)
