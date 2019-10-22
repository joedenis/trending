from trending import data_build


def main():
    world = ["SPY", "VINEX", "VUSTX"]
    sectors = ["XLB", "XLE", "XLF", "XLI", "XLK", "XLP", "XLU", "XLV", "XLY"]
    all_weather = ["SPY", "IEF", "TLT", "GLD", "DBC"]

    stocks = ["BP.L", "NG.L", "AZN.L", "BT-A.L", "GSK.L"]

    crypto = ['BTC-USD', 'ETH-USD']

    # ticker = '^GSPC'
    source = 'yahoo'
    date_start = '2014-09-16'
    # symbol = 'SPX'
    date_end = '2019-10-22'

    for instrument in crypto:
        data_build.main(instrument, source, date_start, date_end, instrument)

if __name__ == "__main__":
    main()
