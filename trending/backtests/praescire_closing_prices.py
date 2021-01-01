import pandas as pd


def praescire_closing_prices(
		path="/home/joe/Dropbox/praescire_database/", filename='Trades database 2019.xlsm',
		sheet_number=2, save_name="PRAESCIRE19.csv"):
	"""
	to create open high low Close adj close volume prices of the praescire price in order to run the tearsheet from
	the backtester
	"""

	trades_database = pd.read_excel(path+filename, sheet_name=sheet_number, skiprows=6)

	closing_prices = trades_database[['Row Labels', 'Fund Value']]

	closing_prices = closing_prices.rename(columns={"Row Labels": "Date", "Fund Value": "Close"}).dropna()
	closing_prices['Close'] = closing_prices['Close'].div(100)
	closing_prices['Open'] = closing_prices['Close']
	closing_prices['High'] = closing_prices['Close']
	closing_prices['Low'] = closing_prices['Close']
	closing_prices['Adj Close'] = closing_prices['Close']
	closing_prices['Volume'] = 100000000

	closing_prices = closing_prices[['Date', 'High', 'Low', 'Open', 'Close', 'Volume', 'Adj Close']]

	closing_prices.to_csv('~/PycharmProjects/trending/trending/data/' + save_name, index=False)

	print(closing_prices)


if __name__ == "__main__":
	praescire_closing_prices(filename='Trades database 2021.xlsm', save_name="PRAESCIRE21.csv")
