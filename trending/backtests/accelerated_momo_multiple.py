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
            self, tickers, bonds_ticker,
            events_queue,
            trade_freq = 21, # we will trade every month
            first_window = 21,  # 1month, 3month and 6month returns in business days
            second_window = 63,
            third_window = 126,
            base_quantity = 100  #needed for how much we invest in the portfolio
    ):
        self.tickers = tickers
        self.risk_free = bonds_ticker
        self.events_queue = events_queue
        self.trade_freq = trade_freq
        self.first_window = first_window
        self.second_window = second_window
        self.third_window = third_window
        self.base_quantity = base_quantity
        self.bars = 0
        # self.invested = False
        # self.invested = dict.fromkeys(tickers, [])  # Use the dictioary to see which asset we are current invested in
        self.prices_df = pd.DataFrame(columns=tickers, dtype=int)

        self.invested = {ticker: False for ticker in tickers}
        # we use a series as we only have one ticker coming in here
        # self.prices_df = pd.Series([])



    # Next up we have to write how to calculate the signals for all three
    # We hold all the incoming price data in a dataframe with 3 columns

    def calculate_signals(self, event):
        if (
            event.type == EventType.BAR and
            event.ticker in self.tickers
        ):
            # print("what type of price is in the event", event.adj_close_price, type(event.adj_close_price))
            # print("Our dataframe looks like this ", self.prices_df)
            self.prices_df = self.prices_df.append({event.ticker: event.adj_close_price}, ignore_index=True)

            # self.prices_df[self.bars] = event.adj_close_price
            if self.bars == 0:
                print (self.prices_df)
                print("printeing the invested dictionary")
                for key, value in self.invested.items():
                    print (key, value)
            # if we have enough bars for the third window
            if self.bars > self.third_window + 1:
                # We only interested in monthly trading
                if self.bars % self.trade_freq == 0:
                    # print(self.prices_df.tail(5))
                    # calculate the 1 month, 3 month, 6 month returns
                    # current_price = self.prices_df.iloc[-1][ticker]
                    returns_dict={}
                    for ticker in tickers:
                        # now we don't want to calculate returns for the risk free asset
                        if ticker not in [self.risk_free]:
                            current_price = self.prices_df[ticker].iloc[-1]
                            one_month = (current_price - self.prices_df[ticker].iloc[-1 - self.first_window]) / current_price
                            three_month = (current_price - self.prices_df[ticker].iloc[-1 - self.second_window]) / current_price
                            six_month = (current_price - self.prices_df[ticker].iloc[-1 - self.third_window]) / current_price

                            returns_dict[ticker] = np.mean([one_month, three_month, six_month])

                    # logic now:  buy the asset with the max momo score when we are not invested
                    best_perfomer = max(returns_dict, key=returns_dict.get)
                    # print(best_perfomer)
                    if returns_dict[best_perfomer] > 0 and not self.invested[best_perfomer]:
                        for investment in getKeysByValue(self.invested, True):
                        #     sell everything that we own
                            print("SELLING %s: %s" % (investment, event.time))
                            signal = SignalEvent(
                                investment, "SLD",
                                suggested_quantity=self.base_quantity
                            )
                            self.events_queue.put(signal)
                            self.invested[investment] = False

                        print("LONG %s: %s " % (best_perfomer, event.time))
                        signal = SignalEvent(
                            best_perfomer, "BOT",
                            suggested_quantity=self.base_quantity
                        )
                        self.events_queue.put(signal)
                        self.invested[best_perfomer] = True

                    #     Othrewise buy bonds if we dont own them already
                    else:
                        if self.invested[self.risk_free] == False:
                            for investment in getKeysByValue(self.invested, True):
                                #     sell everything that we own
                                print("SELLING %s: %s" % (investment, event.time))
                                signal = SignalEvent(
                                    investment, "SLD",
                                    suggested_quantity=self.base_quantity
                                )
                                self.events_queue.put(signal)
                                self.invested[investment] = False

                            print("LONG %s: %s " % (self.risk_free, event.time))
                            signal = SignalEvent(
                                self.risk_free, "BOT",
                                suggested_quantity=self.base_quantity
                            )
                            self.events_queue.put(signal)
                            self.invested[self.risk_free] = True

            self.bars += 1


def run(config, testing, tickers, bonds_ticker, filename):
    # Backtest information
    title = ['Accelerating momentum for AAPL, GOOG, SPY as defensive: 1m, 3m, 6m > 0']
    initial_equity = 10000.0
    start_date = datetime.datetime(2000, 1, 1)
    end_date = datetime.datetime(2014, 1, 1)

    # Use the MAC Strategy
    events_queue = queue.Queue()
    strategy = AcceleratingMomentumStrategy(
        tickers, bonds_ticker, events_queue
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


'''
Get a list of keys from dictionary which has the given value
'''
def getKeysByValue(dictOfElements, valueToFind):
    listOfKeys = list()
    listOfItems = dictOfElements.items()
    for item  in listOfItems:
        if item[1] == valueToFind:
            listOfKeys.append(item[0])
    return  listOfKeys


if __name__ == "__main__":
    # Configuration data
    testing = False

    # unresolved referenece for settings
    config = settings.from_file(
        settings.DEFAULT_CONFIG_FILENAME, testing
    )
    tickers = ["AAPL",'GOOG', 'SPY']
    bonds_ticker = 'SPY'
    filename = None
    run(config, testing, tickers, bonds_ticker, filename)
