import datetime
import calendar
import pandas_market_calendars as mcal


import pandas as pd

from trending import settings

from trending.strategy.base import AbstractStrategy
from trending.event import SignalEvent, EventType
from trending.position_sizer.rebalance import LiquidateRebalancePositionSizer

import queue

from trending.trading_session import TradingSession


class BuyAndHoldStrategy(AbstractStrategy):
    """
    A testing strategy that simply purchases (longs) an asset
    upon first receipt of the relevant bar event and
    then holds until the completion of a backtest.

    We use a monthly rebalance.
    We give it calendars to only trade when markets are open
    """
    def __init__(
        self, ticker, events_queue, calendars
        # base_quantity=100
    ):
        self.ticker = ticker
        self.events_queue = events_queue
        # self.base_quantity = base_quantity
        # counting bars not needed for monthyl trading
        # self.bars = 0
        self.invested = False
        self.calendars = calendars

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

    def calculate_signals(self, event):
        if (
            event.type in [EventType.BAR, EventType.TICK] and
            event.ticker == self.ticker and self._end_of_month_trading_calendar(event.time)
        ):
            ticker = event.ticker
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
    title = ['Buy and Hold monthly rebalance Example on %s' % tickers[0]]

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
    strategy = BuyAndHoldStrategy(tickers[0], events_queue, calendars)

    ticker_weights = {
        "TSLA": 1
    }
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
    tickers = ["TSLA"]
    filename = "/home/joe/Desktop/TSLA.png"
    initial_equity = 22500000.0
    run(config, testing, tickers, filename, initial_equity)
