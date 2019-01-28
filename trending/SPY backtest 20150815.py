# random_forecast.py

import numpy as np
import pandas as pd
import datetime as dt
from trending.backtest import Strategy
import os



class RSIKickInStrategy(Strategy):
    """Derives from Strategy to produce a set of signals that
    are randomly generated long/shorts. Clearly a nonsensical
    strategy, but perfectly acceptable for demonstrating the
    backtesting infrastructure!"""

    def __init__(self, symbol, infobars):
        """Requires the symbol ticker and the pandas DataFrame of bars"""
        self.symbol = symbol
        self.indicators = infobars


    def generate_signals(self):
        """Creates a pandas DataFrame of signals based on entry / exit strategy."""
        signals = pd.DataFrame(index=self.indicators.index)
        signals[['trade_on', 'trade_number', 'in_price', 'stop_out','out_price', 'daily_ret']] = pd.DataFrame(index = signals.index,columns =['trade_on', 'trade_number', 'in_price','stop_out', 'out_price','daily_ret'])
        signals['trade_on']= signals['trade_on'].fillna(0)
        trade_on = 0
        buffer_days = 250
        daily_ret = 0
        trade_counter = 0
        in_price = np.NaN
        out_price = np.NaN
        stop_out = np.NaN
        is_first_day_of_trade = 0
        trades_summary = pd.DataFrame(columns =['trade_number' , 'in_price' , 'out_price', 'trading_days'])
        input_vars = dict(input_RSI_entry_max=30, input_previous_RSI_high_min=65, input_days_since_high_min=8, initial_stop_pct=0.012, basis_points_from_LBB = 10, trailing_stop_activate_pct =0.02, trailing_stop_pct = 0.012)
        for index, row in self.indicators.iloc[buffer_days:, ].iterrows():
            #if index == dt.datetime.strptime('08/10/2013', '%d/%m/%Y'):
            #    print ('a')
            if trade_on == 0:
                daily_ret = 0
                in_price =np.NaN
                out_price = np.NaN
                # RSI limit to be 70 +/- 10
                #min day range to look in [2-10]
                #criteria 1-2: Is the RSI greater than X.  Are we above the 200 DMA
                if (row['Volume'] > 0 and (row['Open'] > row['DMA']) and \
                    #criteria 3-4 : previous RSI high (in period of 3-8 weeks previous) must be greater than Y. Must be N days from previous high
                    self.indicators['RSI'][index - dt.timedelta(days=56): index - dt.timedelta(days=1)].max() > input_vars['input_previous_RSI_high_min'] and \
                        #must be within 10 basis points from LBB
                        row['Low'] <= row['Bollinger Low'] * (input_vars['basis_points_from_LBB']*0.0001 + 1) and \
                            #must have been the first trade since the high RSI
                            signals["trade_on"][self.indicators[self.indicators['RSI'] > input_vars['input_previous_RSI_high_min']][index - dt.timedelta(days=56): index - dt.timedelta(days=1)].index[-1]:index].max() == 0):
                                # PUT TRADE ON
                                trade_on = 1
                                in_price = row['Bollinger Low'] * (input_vars['basis_points_from_LBB']*0.0001 + 1)
                                # initial stop set at 2pct below entry price
                                stop_out = in_price * (1 - input_vars['initial_stop_pct'])
                                lag_index = index
                                trade_start_index = index
                                trade_counter = trade_counter + 1
                                is_first_day_of_trade = 1
                                # calculate daily return.  check if stopped out on same day
                                if row['Low'] < in_price * (1 - input_vars['initial_stop_pct']):
                                    daily_ret = -1* input_vars['initial_stop_pct']
                                    out_price = stop_out
                                else:
                                    daily_ret = row['Close']/in_price -1.0
                                #update trade signals with new trade
                                signals.loc[index,['trade_on','trade_number','in_price', 'stop_out', 'out_price', 'daily_ret']] = [trade_on, trade_counter, in_price, stop_out, out_price, daily_ret]
                #no trade triggered, update signals
                signals.loc[index,['trade_on','trade_number','in_price', 'stop_out', 'out_price', 'daily_ret']] = [trade_on, trade_counter, in_price, stop_out, out_price, daily_ret]
            else:

                #trade is on --> look for where to get out.  Also need to check previous day in case low cam after entry, but only after first day

                #Did we get stopped out day before on first day of trade?
                if (is_first_day_of_trade == 1 and self.indicators['Low'][lag_index] <= stop_out):
                    trade_on = 0
                    is_first_day_of_trade = 0
                    out_price = stop_out
                    trades_record = pd.DataFrame([dict(trade_number = trade_counter, in_price = in_price, out_price = out_price, trading_days = self.indicators[self.indicators['Volume']>0][trade_start_index: index - dt.timedelta(days=1)].index.size, trade_end_date = index),], index = [trade_start_index])
                    trades_summary =trades_summary.append(trades_record)
                    #set prices and rets to 0 since there is no trade today
                    daily_ret = 0
                    in_price = np.NaN
                    out_price = np.NaN
                    signals.loc[index,['trade_on','trade_number','in_price', 'stop_out', 'out_price', 'daily_ret']] = [trade_on, trade_counter, in_price, stop_out, out_price, daily_ret]

                #Did we get stopped out today?
                elif self.indicators['Low'][index] <= stop_out :
                    is_first_day_of_trade = 0
                    out_price = stop_out
                    trades_record = pd.DataFrame([dict(trade_number = trade_counter, in_price = in_price, out_price = out_price, trading_days = self.indicators[self.indicators['Volume']>0][trade_start_index: index - dt.timedelta(days=1)].index.size, trade_end_date = index),], index = [trade_start_index])
                    trades_summary =trades_summary.append(trades_record)
                    daily_ret = (stop_out/self.indicators['Close'][index - dt.timedelta(days = 1)]) -1
                    signals.loc[index,['trade_on','trade_number','in_price', 'stop_out', 'out_price', 'daily_ret']] = [trade_on, trade_counter, in_price, stop_out, out_price, daily_ret]
                    trade_on = 0
                else:
                    #trade continues
                    is_first_day_of_trade = 0
                    out_price = np.NaN
                    daily_ret = (row['Close']/self.indicators['Close'][index - dt.timedelta(days = 1)] ) -1
                    signals.loc[index,['trade_on','trade_number','in_price', 'stop_out', 'out_price', 'daily_ret']] = [trade_on, trade_counter, in_price, stop_out, out_price, daily_ret]
                    # Are we above the threshold needed to activate trailing stop?
                    if (self.indicators['Close'][index]/in_price) -1.0 >  input_vars['trailing_stop_activate_pct']:
                        stop_out = max(stop_out, self.indicators['Close'][index] * (1- input_vars['trailing_stop_pct'] )) # trailing stop at X% below highest settle
                    lag_index = index
        return signals, trades_summary



if __name__ == "__main__":
    # Obtain daily bars of SPY (ETF that generally
    # follows the S&P500) from Quandl (requires 'pip install Quandl'
    # on the command line)

    export_path = os.getcwd() + "\\Datastore\\"
    indicators_filepath = export_path + "spy_indicators.csv"

    export_signals_filepath = export_path + "spy_btest_signals.csv"
    export_summary_filepath = export_path + "spy_btest_summary.csv"

    symbol = 'SPY'

    infobars = pd.read_csv(indicators_filepath)
    infobars['Date'] = pd.to_datetime(infobars['Date'])
    infobars= infobars.set_index(['Date'])

    # Create a set of random forecasting signals for SPY
    rfs = RSIKickInStrategy(symbol, infobars)

    signals, trades_summary = rfs.generate_signals()

    infobars[['trade_on', 'trade_number', 'in_price','stop_out', 'out_price', 'daily_ret']] = signals[['trade_on', 'trade_number', 'in_price','stop_out', 'out_price', 'daily_ret']]
    infobars.to_csv(export_signals_filepath)

    trades_summary.set_index(['trade_number'])
    trades_summary.to_csv(export_summary_filepath)
    print('complete')
    # Create a portfolio of SPY
    #portfolio = MarketOnOpenPortfolio(symbol, bars, signals, initial_capital=100000.0)
    #returns = portfolio.backtest_portfolio()

    #print(returns.tail(10))

