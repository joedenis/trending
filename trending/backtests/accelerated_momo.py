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
            self, ticker,
            events_queue,
            trade_freq = 21, # we will trade every month
            first_window = 21,  # 1month, 3month and 6month returns in business days
            second_window = 63,
            third_window = 126,
            base_quantity = 100  #needed for how much we invest in the portfolio
    ):
        self.ticker = ticker
        self.events_queue = events_queue
        self.trade_freq = trade_freq
        self.first_window = first_window
        self.second_window = second_window
        self.third_window = third_window
        self.base_quantity = base_quantity
        self.bars = 0
        self.invested = False
        self.prices_df = pd.DataFrame(columns=[ticker], dtype=int)

        # we use a series as we only have one ticker coming in here
        # self.prices_df = pd.Series([])



    # Next up we have to write how to calculate the signals for all three
    # we start by an allocation to one asset.

    def calculate_signals(self, event):
        if (
            event.type == EventType.BAR and
            event.ticker == self.ticker
        ):
            # print("what type of price is in the event", event.adj_close_price, type(event.adj_close_price))
            # print("Our dataframe looks like this ", self.prices_df)
            self.prices_df = self.prices_df.append({event.ticker: event.adj_close_price}, ignore_index=True)

            # self.prices_df[self.bars] = event.adj_close_price
            if self.bars == 0:
                print (self.prices_df)
            # if we have enough bars for the third window
            if self.bars > self.third_window + 1:
                if self.bars % self.trade_freq == 0:
                    # print(self.prices_df.tail(5))
                    # calculate the 1 month, 3 month, 6 month returns
                    # current_price = self.prices_df.iloc[-1][ticker]
                    current_price = self.prices_df.iloc[-1]
                    one_month = (current_price - self.prices_df.iloc[-1 - self.first_window]) / current_price
                    three_month = (current_price - self.prices_df.iloc[-1 - self.second_window]) / current_price
                    six_month = (current_price - self.prices_df.iloc[-1 - self.third_window]) / current_price

                    accelerating_momo = np.mean([one_month, three_month, six_month])

                    if accelerating_momo > 0 and not self.invested:
                        print("LONG %s: %s " % (self.ticker, event.time))
                        signal = SignalEvent(
                            self.ticker, "BOT",
                            suggested_quantity=self.base_quantity
                        )
                        self.events_queue.put(signal)
                        self.invested = True
                    elif accelerating_momo < 0 and self.invested:
                        print("SELLING %s: %s" %(self.ticker, event.time))
                        signal = SignalEvent(
                            self.ticker, "SLD",
                            suggested_quantity=self.base_quantity
                        )
                        self.events_queue.put(signal)
                        self.invested = False
            self.bars += 1


def run(config, testing, tickers, filename):
    # Backtest information
    title = ['Accelerating momentum for SPY: 1m, 3m, 6m > 0']
    initial_equity = 10000.0
    start_date = datetime.datetime(2000, 1, 1)
    end_date = datetime.datetime(2014, 1, 1)

    # Use the MAC Strategy
    events_queue = queue.Queue()
    strategy = AcceleratingMomentumStrategy(
        tickers[0], events_queue
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
    tickers = ["SPY", "SPY"]
    filename = None
    spy_momo = run(config, testing, tickers, filename)

    print(spy_momo['positions'])


