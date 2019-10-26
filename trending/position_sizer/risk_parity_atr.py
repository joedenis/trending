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
		Size the order to reflect the dollar-weighting of the
		current equity account size based on pre-specified
		ticker weights.
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
		else:

			weight = self.ticker_weights[ticker]
			# Determine total portfolio value, work out dollar weight
			# and finally determine integer quantity of shares to purchase
			price = portfolio.price_handler.tickers[ticker]["adj_close"]
			price_unadjusted = portfolio.price_handler.tickers[ticker]["close"]

			# test = initial_order.quantity
			atr_for_adjusted = int((initial_order.quantity / price_unadjusted) * price)


			equity = PriceParser.display(portfolio.equity)
			# atr_base_unit = PriceParser.display(initial_order.quantity)

			atr_for_adjusted = PriceParser.display(atr_for_adjusted)

			quantity_atr_adjusted = int(floor((equity * weight) / atr_for_adjusted))

			initial_order.quantity = quantity_atr_adjusted
		return initial_order
