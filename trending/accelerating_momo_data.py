from trending import data_build


def main():
    world = ["SPY", "VINEX", "VUSTX"]
    sectors = ["XLB", "XLE", "XLF", "XLI", "XLK", "XLP", "XLU", "XLV", "XLY"]
    all_weather = ["SPY", "IEF", "TLT", "GLD", "DBC"]

    stocks = ["BP.L", "ITV.L", "AZN.L", "BT-A.L", "GSK.L"]

    # ticker = '^GSPC'
    source = 'yahoo'
    date_start = '1999-01-01'
    # symbol = 'SPX'
    date_end = '2019-10-17'

    for instrument in all_weather:
        data_build.main(instrument, source, date_start, date_end, instrument)

if __name__ == "__main__":
    main()
