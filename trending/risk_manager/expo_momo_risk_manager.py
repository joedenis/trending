from trending.risk_manager.base import AbstractRiskManager
from trending.event import OrderEvent


class ExpoMomoRiskManager(AbstractRiskManager):
	"""
	an order can only go through if we have cash in the account to buy
	orders with 0 quantity are not executed. (this happens when we checked for a rebalance but the rebalance threshold
	was not met.

	liquiated orders the initial cash is increased

	"""
	def __init__(self, initial_equity):
		self.current_cash = initial_equity

	def refine_orders(self, portfolio, sized_order):

		ticker = sized_order.ticker
		quantity = sized_order.quantity
		price = portfolio.price_handler.tickers[ticker]["adj_close"]

		proposed_cost = price * quantity

		if sized_order.action == "SLD":
			order_event = OrderEvent(
				ticker,
				sized_order.action,
				quantity
			)
		# 	increase the current cash
			self.current_cash += proposed_cost
			return [order_event]
		elif quantity == 0:
			return []
		elif proposed_cost < self.current_cash:
			order_event = OrderEvent(
				ticker,
				sized_order.action,
				quantity
			)
			self.current_cash -= proposed_cost
			return [order_event]
		else:
			# not enough money to buy the stock
			# print("NO MONEY TO BUY FROM THE RISKMANAGER SO CANCELLING THE ORDER")
			return []



