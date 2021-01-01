from trending import data_build
from pathlib import Path
import os

def main():
    world = ["SPY", "VINEX", "VUSTX"]
    sectors = ["XLB", "XLE", "XLF", "XLI", "XLK", "XLP", "XLU", "XLV", "XLY"]
    all_weather = ["SPY", "IEF", "TLT", "GLD", "DBC"]

    stocks = ["BP.L", "NG.L", "AZN.L", "BT-A.L", "GSK.L", "ITV.L"]

    us_titans = ["TSLA", "FB", "AMZN", "AAPL", "MSFT", "SPY"]

    crypto = ['BTC-USD', 'ETH-USD']

    # ticker = '^GSPC'
    source = 'yahoo'
    date_start = '1999-09-16'
    # symbol = 'SPX'
    date_end = '2020-12-27'

    for instrument in sectors:
        data_build.main(instrument, source, date_start, date_end, instrument, export_path=str(Path(os.getcwd()) / 'data') +'/')

if __name__ == "__main__":
    main()
