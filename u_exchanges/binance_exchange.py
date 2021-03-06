import typing
import asyncio
from binance.client import Client
from binance.exceptions import BinanceAPIException

from . import types
from .base import BaseExchange, logger


class BinanceAssetBalance(types.AssetBalance):
    def __init__(self, x) -> None:
        self.free = float(x['free'])
        self.borrowed = float(x['borrowed']) + float(x['interest'])
        self.total = float(x['totalAsset'])


class BinanceMarginAccount(types.MarginAccount):
    def __init__(self, **kwargs) -> None:
        x = kwargs
        base_asset = x['baseAsset']
        quote_asset = x['quoteAsset']
        self.base_asset = base_asset['asset']
        self.quote_asset = quote_asset['asset']
        self.symbol = x['symbol']
        self.base_asset_balance = BinanceAssetBalance(base_asset)
        self.quote_asset_balance = BinanceAssetBalance(quote_asset)
        self.liquidation_price = float(x['liquidatePrice'])
        self.margin_ratio = float(x['marginRatio'])


class BinanceLoanInfo(types.LoanInfo):
    def __init__(self, asset, max_loan_info, interest_info) -> None:
        self.asset = asset
        self.rate = float(interest_info['dailyInterestRate'])
        self.available = float(max_loan_info['amount'])


class BinanceClient(Client):
    def interest_rate_history(self, **params):
        return self._request_margin_api('get', 'margin/interestRateHistory', signed=True, data=params)

    def get_price(
        self, market: str, amount: int = None, length=4
    ) -> typing.Optional[float]:
        # return await self.get_price_ws(market, amount, length)
        result = self.get_all_tickers()
        market_price = [x for x in result if x["symbol"] == market.upper()]
        pp = None
        if market_price:
            pp = float(market_price[0]["price"])
            if amount:
                as_string = format(pp, ".8e").split("e")[1]
                pps = float(amount)
                if int(as_string) > 0:
                    return pps
                return pps * 10 ** (int(as_string) - length + 1)
        return pp

    def cancel_margin_open_orders(self, **kwargs):
        return self._request_margin_api('delete', 'margin/openOrders', signed=True, data=kwargs)


def process_places(exchange_info, symbol):
    results = [
        x for x in exchange_info["symbols"] if x["symbol"].lower() == symbol.lower()
    ]
    if results:
        result = results[0]
        price_filter = [
            x for x in result["filters"] if x["filterType"] == "PRICE_FILTER"
        ]
        quantity_filter = [
            x for x in result["filters"] if x["filterType"] == "LOT_SIZE"
        ]
        minimum_filter = [
            x for x in result["filters"] if x["filterType"] == "MIN_NOTIONAL"
        ]
        def get_place(x): return abs(int(format(float(x), ".8e").split("e")[1]))
        price_places = get_place(price_filter[0]["tickSize"])
        quantity_places = get_place(quantity_filter[0]["stepSize"])
        minimum_trade_price = None
        value = None
        if minimum_filter:
            value = minimum_filter[0].get("minNotional")
        if not value:
            value = quantity_filter[0]["stepSize"]

        if value:
            minimum_trade_price = float(value)
        return {
            "price_places": f"%.{price_places}f",
            "places": f"%.{quantity_places}f",
            "difference": 1 * 10 ** -price_places,
            "stepSize": float(quantity_filter[0]["stepSize"]),
            "minimum": minimum_trade_price,
            "contractSize": result.get("contractSize"),
        }


class BinanceExchange(BaseExchange):
    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)

    @property
    def client(self) -> BinanceClient:
        return BinanceClient(api_key=self.api_key, api_secret=self.api_secret)

    async def update_price_and_decimal_places(self, symbol: str, raw=False):
        if not raw:
            exchange_info = self.client.get_exchange_info()
            result = process_places(exchange_info, symbol)
            if result:
                self.price_places = result["price_places"]
                self.decimal_places = result["places"]
                self.difference = result["difference"]
                self.step_size = result["stepSize"]
                self.minimum = result["minimum"] + (self.step_size * 2)
                self.updated = True

    async def get_margin_accounts(self, symbol=None) -> typing.List[types.MarginAccount]:
        if symbol:
            account = self.client.get_isolated_margin_account(symbols=symbol)
            return BinanceMarginAccount(**account['assets'][0])
        else:
            account = self.client.get_isolated_margin_account()
            return [BinanceMarginAccount(**x) for x in account['assets']]

    async def get_loanable_amount(self, symbol: str) -> typing.List[types.LoanInfo]:
        symbol_info = self.client.get_isolated_margin_symbol(symbol=symbol)
        max_loan_helper = lambda **x: self.client_helper('get_max_margin_loan', **x)

        def interest_rate_helper(x):
            return self.client_helper('interest_rate_history', asset=x, limit=1)
        base_loan, quote_loan, base_rate, quote_rate = await asyncio.gather(
            max_loan_helper(asset=symbol_info['base'], isolatedSymbol=symbol),
            max_loan_helper(asset=symbol_info['quote'], isolatedSymbol=symbol),
            interest_rate_helper(symbol_info['base']),
            interest_rate_helper(symbol_info['quote'])
        )

        return [
            BinanceLoanInfo(symbol_info['base'], base_loan, base_rate[0]),
            BinanceLoanInfo(symbol_info['quote'], quote_loan, quote_rate[0])
        ]

    async def borrow_loan(self, asset: str, symbol: str, amount: float) -> bool:
        try:
            result = self.client.create_margin_loan(asset=asset, amount=amount, isIsolated='TRUE', symbol=symbol)
            return True
        except BinanceAPIException as e:
            logger.exception(e)
            return False

    async def repay_loan(self, asset: str, symbol: str, amount: float) -> bool:
        try:
            result = self.client.repay_margin_loan(asset=asset, amount=amount, symbol=symbol, isIsolated='TRUE')
            return True
        except BinanceAPIException as e:
            logger.exception(e)
            return False

    async def create_single_order(self, symbol: str, side: str, quantity: float, price: float, notional: float = None, raw=False, **kwargs):
        _, current_price = await asyncio.gather(self.update_price_and_decimal_places(symbol, raw=raw), self.client_helper('get_price', symbol))

        def get_type(params):
            if params["side"]:
                if params["side"].upper() == "BUY":
                    if current_price > params["price"]:
                        return "TAKE_PROFIT_LIMIT"
                    return "STOP_LOSS_LIMIT"
                if params["side"].upper() == "SELL":
                    if (
                        params.get('kind') and params.get('kind').lower() == "long"
                        and current_price < params["price"]
                    ):
                        return "TAKE_PROFIT_LIMIT"
            return "STOP_LOSS_LIMIT"

        def build_stop(u):
            if u["side"]:
                if u["side"].upper() == "BUY":
                    return u["price"] - self.difference
                return u["price"] + self.difference
            if u.get('kind').lower() == "long":
                # if current_price > u["price"]:
                #     return u["price"] - self.difference
                return u["price"] - self.difference
            return u["price"] + self.difference
        new_quantity = quantity
        if notional:
            new_quantity = notional / current_price + self.minimum
        v = {
            "symbol": symbol.upper(),
            "price": float(self.price_places % price),
            "quantity": float(self.decimal_places % new_quantity),
            "side": side.upper(),
            "type": "LIMIT",
            "timeInForce": "GTC",
            "sideEffectType": "MARGIN_BUY",
        }
        if kwargs.get("repay"):
            v["sideEffectType"] = "AUTO_REPAY"
        if kwargs.get("stop"):
            v["stopPrice"] = float(self.price_places % build_stop({'side': side, 'price': v['price'], **kwargs}))
            v["sideEffectType"] = "AUTO_REPAY"
            if kwargs.get("borrow"):
                v["sideEffectType"] = "MARGIN_BUY"
            v["type"] = get_type({'side': side, 'price': v['price']})
        if kwargs.get("is_market"):
            v["type"] = "MARKET"
            del v["price"]
        if raw:
            return v
        result = self.client.create_margin_order(isIsolated="TRUE", **v)
        return result['orderId']

    async def bulk_create_orders(self, symbol: str, orders: typing.List[typing.Any]):
        await self.update_price_and_decimal_places(symbol)
        _orders = await asyncio.gather(*[self.create_single_order(**{'raw': True, 'symbol': symbol, **x}) for x in orders])
        results = await asyncio.gather(*[self.client_helper('create_margin_order', isIsolated='TRUE', **x) for x in _orders])
        return results

    async def cancel_single_order(self, symbol: str, order_id):
        self.client.cancel_margin_order(symbol=symbol.upper(), orderId=order_id, isolated=True)

    async def bulk_cancel_orders(self, symbol: str, order_ids: typing.List[typing.Any]):
        await asyncio.gather(*[self.client_helper('cancel_margin_orders', symbol=symbol, orderId=x, isolated=True) for x in order_ids])

    async def cancel_open_orders(self, symbol: str):
        self.client.cancel_margin_open_orders(symbol=symbol, isIsolated="TRUE")

    async def get_open_orders(self, symbol: str):
        return self.client.get_open_margin_orders(symbol=symbol, isIsolated="TRUE")

    async def get_closed_orders(self, symbol: str):
        orders = self.client.get_margin_trades(symbol=symbol, isIsolated='TRUE')
        return orders
