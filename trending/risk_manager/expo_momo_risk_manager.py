from trending.risk_manager.base import AbstractRiskManager
from trending.event import OrderEvent


class ExpoMomoRiskManager(AbstractRiskManager):
	"""
	an order can only go through if we have cash in the account to buy

	"""

	def refine_orders(self, portfolio, sized_order):

		cash_left = portfolio.cur_cash

		ticker = sized_order.ticker
		quantity = sized_order.quantity
		price = portfolio.price_handler.tickers[ticker]["adj_close"]

		proposed_cost = price * quantity

		if proposed_cost < cash_left:
			order_event = OrderEvent(
				ticker,
				sized_order.action,
				quantity
			)
			return [order_event]
		else:
			# not enough money to buy the stock
			# print("NO MONEY TO BUY FROM THE RISKMANAGER SO CANCELLING THE ORDER")
			return []



