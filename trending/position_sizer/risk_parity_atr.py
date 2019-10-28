from math import floor

from .base import AbstractPositionSizer
from trending.price_parser import PriceParser


class RiskParityATRPositionSizer(AbstractPositionSizer):
	"""
	Carries out a periodic full liquidation and rebalance of
	the Portfolio.

	This is achieved by determining whether an order type type
	is "EXIT" or "BOT/SLD".

	If the former, the current quantity of shares in the ticker
	is determined and then BOT or SLD to net the position to zero.

	If the latter, the current quantity of shares to obtain is
	determined by prespecified weights and adjusted to reflect
	current account equity.
	"""
	def __init__(self, ticker_weights):
		self.ticker_weights = ticker_weights

	def size_order(self, portfolio, initial_order):
		"""
		if the order is to EXIT we exit
		otherwise if we already have a position, we look to rebalance
		"""
		ticker = initial_order.ticker
		if initial_order.action == "EXIT":
			# Obtain current quantity and liquidate
			cur_quantity = portfolio.positions[ticker].quantity
			if cur_quantity > 0:
				initial_order.action = "SLD"
				initial_order.quantity = cur_quantity
			else:
				initial_order.action = "BOT"
				initial_order.quantity = cur_quantity
		elif portfolio.positions[ticker].quantity is not None and portfolio.positions[ticker].quantity > 0:
			"""
						rebalance if we already have a position
			"""
			weight = self.ticker_weights[ticker]
			# Determine total portfolio value, work out dollar weight
			# and finally determine integer quantity of shares to purchase
			price = portfolio.price_handler.tickers[ticker]["adj_close"]
			# price_unadjusted = portfolio.price_handler.tickers[ticker]["close"]

			# test = initial_order.quantity
			# atr_for_adjusted = int((initial_order.quantity / price_unadjusted) * price)

			equity = PriceParser.display(portfolio.equity)
			current_cash = PriceParser.display(portfolio.cur_cash)
			print("current cash is", current_cash)
			# atr_base_unit = PriceParser.display(initial_order.quantity)

			atr_for_adjusted = PriceParser.display(initial_order.quantity)

			quantity_atr_adjusted = int(floor((equity * weight) / atr_for_adjusted))

			current_position = portfolio.positions[ticker].quantity

			percentage_difference = (current_position - quantity_atr_adjusted) / quantity_atr_adjusted

			# if the position weights have changed by over 10 percent we adjust the portfolio.
			if abs(percentage_difference) > 0.1:
				if current_position > quantity_atr_adjusted:
					initial_order.action = "SLD"
					initial_order.quantity = current_position - quantity_atr_adjusted
				else:
					initial_order.quantity = quantity_atr_adjusted - current_position
			else:
				initial_order.quantity = 0

		else:
			weight = self.ticker_weights[ticker]
			# Determine total portfolio value, work out dollar weight
			# and finally determine integer quantity of shares to purchase
			price = portfolio.price_handler.tickers[ticker]["adj_close"]
			# price_unadjusted = portfolio.price_handler.tickers[ticker]["close"]

			# test = initial_order.quantity
			# atr_for_adjusted = int((initial_order.quantity / price_unadjusted) * price)


			equity = PriceParser.display(portfolio.equity)
			current_cash = PriceParser.display(portfolio.cur_cash)
			print("current cash is", current_cash)
			# atr_base_unit = PriceParser.display(initial_order.quantity)

			atr_for_adjusted = PriceParser.display(initial_order.quantity)

			quantity_atr_adjusted = int(floor((equity * weight) / atr_for_adjusted))

			initial_order.quantity = quantity_atr_adjusted
		return initial_order
