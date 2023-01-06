import datetime

from trending import settings

from trending.strategy.base import AbstractStrategy
from trending.event import SignalEvent, EventType

import queue

from trending.trading_session import TradingSession


class BuyAndHoldStrategy(AbstractStrategy):
    """
    A testing strategy that simply purchases (longs) an asset
    upon first receipt of the relevant bar event and
    then holds until the completion of a backtest.
    """
    def __init__(
        self, ticker, events_queue,
        base_quantity=100
    ):
        self.ticker = ticker
        self.events_queue = events_queue
        self.base_quantity = base_quantity
        self.bars = 0
        self.invested = False

    def calculate_signals(self, event):
        if (
            event.type in [EventType.BAR, EventType.TICK] and
            event.ticker == self.ticker
        ):
            if not self.invested and self.bars == 0:
                signal = SignalEvent(
                    self.ticker, "BOT",
                    suggested_quantity=self.base_quantity
                )
                self.events_queue.put(signal)
                self.invested = True
            self.bars += 1


def run(config, testing, tickers, _filename):

    # Backtest information
    title = ['Buy and Hold Example on %s' % tickers[0]]
    initial_equity = 850000.0
    start_date = datetime.datetime(2020, 1, 1)

    todays_month = int(datetime.datetime.today().strftime("%m"))
    todays_day = int(datetime.datetime.today().strftime("%d"))
    end_date = datetime.datetime(2020, todays_month, todays_day)

    # Use the Buy and Hold Strategy
    events_queue = queue.Queue()
    strategy = BuyAndHoldStrategy(tickers[0], events_queue)

    # Set up the backtest
    backtest = TradingSession(
        config, strategy, tickers,
        initial_equity, start_date, end_date,
        events_queue, title=title
    )
    results = backtest.start_trading(testing=testing, filename=_filename)
    return results


if __name__ == "__main__":
    # Configuration data
    testing = False
    config = settings.from_file(
        settings.DEFAULT_CONFIG_FILENAME, testing
    )
    tickers = ["PRAESCIRE23"]
    filename = "/home/joe/Desktop/PRAESCIRE23.png"
    run(config, testing, tickers, filename)
