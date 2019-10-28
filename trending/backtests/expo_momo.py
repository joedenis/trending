# TODO we have the ranking working and just going through the rankings at the end of the month and buying if we have cash from a risk manager
# todo but the portfolio is not updating? The tearsheet is incorrect --- needs looking into!


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

from trending.risk_manager.example import ExampleRiskManager
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
    A testing strategy that simply purchases (longs) an asset
    upon first receipt of the relevant bar event and
    then holds until the completion of a backtest.

    We use a monthly rebalance.
    We give it calendars to only trade when markets are open
    """
    def __init__(
        self, tickers, events_queue, calendars,
            window=90, atr_period=20, index_filter="SPY"
        # base_quantity=100
    ):
        self.tickers = tickers
        self.index_ticker = index_filter
        self.events_queue = events_queue
        """
        keep track of the prices we have seen for a given day
        """

        self.time = None
        self.latest_prices = np.full(len(self.tickers), -1.0)


        # index 200dma calculation:
        self.index_dma_window = 200
        self.index_prices = deque(maxlen=self.index_dma_window)
        self.index_dma = False

        # TODO do we need a invested array

        # self.base_quantity = base_quantity
        # counting bars not needed for monthyl trading
        self.bars = 0
        self.invested = False
        self.calendars = calendars
        self.window = window
        self.sma_days_for_stocks = 100

        self.atr_period = atr_period

        self.tickers_invested = self._create_invested_list()

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

    #     creating high lows for asset calculations
    #     self.high_lows = {}
    #     for ticker in tickers:
    #         self.high_lows[ticker] = dict.fromkeys(['today_high', 'today_low', 'yes_close'])

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
            self.bars += 1
            self._set_correct_time_and_price(event)

            #  IF IT IS THE INDEX, THEN WE ONLY USE TO CALCULATE THE 200DAY MOVING AVERAGE
            if event.ticker == self.index_ticker:
                self.index_prices.append(event.adj_close_price)
                if  len(self.index_prices) == self.index_dma_window:
                    close = self.index_prices[-1]
                    are_we_above = self.index_prices[-1] > np.mean(self.index_prices)
                    self.index_dma = self.index_prices[-1] > np.mean(self.index_prices)


            ticker = event.ticker
            # add closing prices to prices queue
            self.ticker_bars[event.ticker].append(event.adj_close_price)
            self.ticker_bars_unadj[event.ticker].append((event.close_price))

            # add todays prices prices and yesterdays prices
            # first we move the old price
            # self.high_lows[event.ticker]['yes_high'] = self.high_lows[event.ticker]['today_high']
            # self.high_lows[event.ticker]['yes_close'] = self.high_lows[event.ticker]['today_low']
            # today_high = event.high_price
            # today_high =


            self.high_lows[event.ticker]['today_high'] = int(event.high_price * event.adj_close_price / event.close_price)
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
                    self.atr[ticker] = atr_series


            # can only trade if all tickers have more than 90 days
            can_trade = True
            for ticker in self.ticker_bars:
                if len(self.ticker_bars[ticker]) < self.window or len(self.ticker_bars[ticker]) < self.sma_days_for_stocks:
                    can_trade = False
                    if not can_trade:
                        break
            #  only trade if end of month and we have seen all price observations for that day

            # if can_trade:
            #     print("ALL tickers have windows greater than", self.window, "or", self.sma_days_for_stocks)
            #
            #     todays_price = self.ticker_bars[ticker][-1]
            #     just_80 = list(itertools.islice(self.ticker_bars[ticker], 10, 90))
            #     last = just_80[79]

            """
            Has the stock had a 15% move in the last 100 days if it has we cant buy
            """

            if can_trade:
                all_days =list(itertools.islice(self.ticker_bars[ticker], 0, len(self.ticker_bars[ticker])))
                all_days = np.asarray(all_days, dtype=np.float32)

                # difference_array = np.diff(all_days)

                percentage_moves = np.diff(all_days) / all_days[1:] * 100
                percentage_moves = abs(percentage_moves)
                max_move = np.max(percentage_moves)
                if max_move > 15.0:
                    can_trade = False


            if self.index_dma and can_trade and \
                    self._end_of_month_trading_calendar(event.time) and \
                    all(self.latest_prices > -1.0):

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
                    # closing_prices = list(self.ticker_bars[ticker])
                    closing_prices = list(itertools.islice(self.ticker_bars[ticker], self.sma_days_for_stocks - self.window, self.sma_days_for_stocks))
                    momenta[ticker] = self.expo_momentum(closing_prices)

                # momenta_df = pd.DataFrame(list(momenta.items), columns=['Asset', 'Momentum'])
                # momenta_df = momenta_df.sort_values(by = 'Momentum')

                # remove the index ticker from the table as we won't buy that
                momenta.pop(self.index_ticker, None)

                n = 2
                top_n = {key:momenta[key] for key in sorted(momenta, key=momenta.get, reverse=True)[:n]}

                top_assets = list(top_n.keys())


                # print(top_assets[0:int(n/2) - 1])


                """
                if we have seen all the stocks.
                Then we want to buy the ones in our top list.
                first we need to see how much money we have in the portfolio
                """
                # size = int(self.atr[ticker].iloc[-1])
                #
                # long_signal = SignalEvent(ticker, "BOT", size)
                # # we need a suggested quantity in the SignalEvent above,  that is done with the risk system
                # self.events_queue.put(long_signal)

                """
                what about iterating through the assets we need to buy and places signals to buy
                """

                for ticker in top_assets:
                    size = int(self.atr[ticker].iloc[-1])

                    long_signal = SignalEvent(ticker, "BOT", size)
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

    year_start = 2013
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





    years = list(range(year_start, year_end + 1))
    calendars = get_dict_of_trading_calendars(years, cal='LSE')





    # Use the Buy and Hold Strategy
    strategy = ExponentialMomentum(tickers, events_queue, calendars)


    risk_per_stock = 0.001

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
    tickers = ["BP.L", "GSK.L", "ITV.L", "NG.L", "SPY"]

    filename = "/home/joe/Desktop/expo_momo.png"
    initial_equity = 100000.0
    run(config, testing, tickers, filename, initial_equity)
