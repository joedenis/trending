from __future__ import print_function

from enum import Enum


EventType = Enum("EventType", "TICK BAR SIGNAL ORDER FILL SENTIMENT")

"""enumeration type where TICK = 1, BAR = 2, SIGNAL = 3, ORDER = 4, FILL = 5, SENTIMENT = 6 """

class Event(object):
    """
    Event is base class providing an interface for all subsequent
    (inherited) events, that will trigger further events in the
    trading infrastructure.
    """
    @property
    def typename(self):
        return self.type.name



class BarEvent(Event):
    """
    Handles the event of receiving a new market
    open-high-low-close-volume bar, as would be generated
    via common data providers such as Yahoo Finance.
    """
    def __init__(
        self, ticker, time, period,
        open_price, high_price, low_price,
        close_price, volume, adj_close_price=None
    ):
        """
        Initialises the BarEvent.

        Parameters:
        ticker - The ticker symbol, e.g. 'GOOG'.
        time - The timestamp of the bar
        period - The time period covered by the bar in seconds
        open_price - The unadjusted opening price of the bar
        high_price - The unadjusted high price of the bar
        low_price - The unadjusted low price of the bar
        close_price - The unadjusted close price of the bar
        volume - The volume of trading within the bar
        adj_close_price - The vendor adjusted closing price
            (e.g. back-adjustment) of the bar

        Note: It is not advised to use 'open', 'close' instead
        of 'open_price', 'close_price' as 'open' is a reserved
        word in Python.
        """
        self.type = EventType.BAR  #uses the enumeration so EventType.BAR = 2
        self.ticker = ticker
        self.time = time
        self.period = period
        self.open_price = open_price
        self.high_price = high_price
        self.low_price = low_price
        self.close_price = close_price
        self.volume = volume
        self.adj_close_price = adj_close_price
        self.period_readable = self._readable_period()

    def _readable_period(self):
        """
        Creates a human-readable period from the number
        of seconds specified for 'period'.

        For instance, converts:
        * 1 -> '1sec'
        * 5 -> '5secs'
        * 60 -> '1min'
        * 300 -> '5min'

        If no period is found in the lookup table, the human
        readable period is simply passed through from period,
        in seconds.
        """
        lut = {
            1: "1sec",
            5: "5sec",
            10: "10sec",
            15: "15sec",
            30: "30sec",
            60: "1min",
            300: "5min",
            600: "10min",
            900: "15min",
            1800: "30min",
            3600: "1hr",
            86400: "1day",
            604800: "1wk"
        }
        if self.period in lut:
            return lut[self.period]
        else:
            return "%ssec" % str(self.period)

    def __str__(self):
        format_str = "Type: %s, Ticker: %s, Time: %s, Period: %s, " \
            "Open: %s, High: %s, Low: %s, Close: %s, " \
            "Adj Close: %s, Volume: %s" % (
                str(self.type), str(self.ticker), str(self.time),
                str(self.period_readable), str(self.open_price),
                str(self.high_price), str(self.low_price),
                str(self.close_price), str(self.adj_close_price),
                str(self.volume)
            )
        return format_str


    """printable representation of the object"""
    def __repr__(self):
        return str(self)

