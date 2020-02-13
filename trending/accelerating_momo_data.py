from trending import data_build
import os


def get_list_tickers(folder='/home/joe/PycharmProjects/trending/data'):
	path = folder
	files = [os.path.splitext(filename)[0] for filename in os.listdir(path)]

	return files


def main():
	world = ["SPY", "VINEX", "VUSTX"]
	sectors = ["XLB", "XLE", "XLF", "XLI", "XLK", "XLP", "XLU", "XLV", "XLY"]
	all_weather = ["SPY", "IEF", "TLT", "GLD", "DBC"]
	all_weather_2xleveraged = ["SSO", "UST", "UBT", "DGP", "DBC", "FLGE"]

	stocks = ["BP.L", "NG.L", "AZN.L", "BT-A.L", "GSK.L", "ITV.L"]

	us_titans = ["TSLA", "FB", "AMZN", "AAPL", "MSFT"]

	crypto = ['BTC-USD', 'ETH-USD']

	all_us_tickers = get_list_tickers()

	# ticker = '^GSPC'
	source = 'yahoo'
	date_start = '1999-09-16'
	# symbol = 'SPX'
	date_end = '2019-12-31'

	export_path = '/home/joe/PycharmProjects/trending/data/full_data/'
	export_path = '/home/joe/PycharmProjects/trending/trending/data/'

	for instrument in all_weather:
		print("Getting ticker:", instrument)
		data_build.main(instrument, source, date_start, date_end, instrument, export_path)
		print("Completed:", instrument)


if __name__ == "__main__":
	main()
