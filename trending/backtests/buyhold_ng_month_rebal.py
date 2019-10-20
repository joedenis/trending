import datetime
import calendar

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
    """
    def __init__(
        self, ticker, events_queue,
        # base_quantity=100
    ):
        self.ticker = ticker
        self.events_queue = events_queue
        # self.base_quantity = base_quantity
        # counting bars not needed for monthyl trading
        # self.bars = 0
        self.invested = False

    def _end_of_month(self, cur_time):
        """
		Determine if the current day is at the end of the month.
		"""
        cur_day = cur_time.day
        end_day = calendar.monthrange(cur_time.year, cur_time.month)[1]
        return cur_day == end_day

    def calculate_signals(self, event):
        if (
            event.type in [EventType.BAR, EventType.TICK] and
            event.ticker == self.ticker and self._end_of_month(event.time)
        ):
            ticker = event.ticker
            if self.invested:
                liquidate_signal = SignalEvent(ticker, "EXIT")
                self.events_queue.put(liquidate_signal)
            long_signal = SignalEvent(ticker, "BOT")
            self.events_queue.put(long_signal)

            self.invested = True

def run(config, testing, tickers, _filename, initial_equity):
    # Backtest information
    title = ['Buy and Hold monthly rebalance Example on %s' % tickers[0]]

    start_date = datetime.datetime(2014, 1, 1)

    todays_month = int(datetime.datetime.today().strftime("%m"))
    todays_day = int(datetime.datetime.today().strftime("%d"))
    end_date = datetime.datetime(2019, todays_month, todays_day)

    # Use the Buy and Hold Strategy
    events_queue = queue.Queue()
    strategy = BuyAndHoldStrategy(tickers[0], events_queue)

    ticker_weights = {
        "GSK.L": 1
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
    tickers = ["GSK.L"]
    filename = "/home/joe/Desktop/GSK.png"
    initial_equity = 22500000.0
    run(config, testing, tickers, filename, initial_equity)
