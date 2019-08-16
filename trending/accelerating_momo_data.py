from trending import data_build


def main():
    world = ["SPY", "VINEX", "VUSTX"]

    # ticker = '^GSPC'
    source = 'yahoo'
    date_start = '1999-01-01'
    # symbol = 'SPX'
    date_end = '2019-08-11'

    for instrument in world:
        data_build.main(instrument, source, date_start, date_end, instrument)

if __name__ == "__main__":
    main()
