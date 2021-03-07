import typing
import asyncio
from binance.client import Client
from binance.exceptions import BinanceAPIException

from . import types, utils
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
        self.balance = {self.quote_asset: self.quote_asset_balance, self.base_asset: self.base_asset_balance}


class BinanceLoanInfo(types.LoanInfo):
    def __init__(self, asset, max_loan_info, interest_info) -> None:
        self.asset = asset
        self.rate = float(interest_info['dailyInterestRate'])
        self.available = float(max_loan_info['amount'])


class BinanceBalanceType(types.BalanceType):
    def __init__(self, x) -> None:
        self.asset = x['asset']
        self.available = float(x['free'])
        self.balance = float(x['free'])
        self.locked = float(x['locked'])


class BinanceFuturePosition(types.FuturePosition):
    def __init__(self, x, coin_type) -> None:
        self.symbol = x['symbol']
        self.future_type = 'coin' if coin_type else 'usdt'
        self.size = abs(float(x['positionAmt']))
        self.entry = float(x['entryPrice'])
        self.pnl = float(x['unRealizedProfit'])
        self.liquidation_price = float(x['liquidationPrice'])
        self.leverage = float(x['leverage'])
        self.margin_type = x['marginType']
        self.kind = x['positionSide'].lower()
        self.mark_price = float(x['markPrice'])


class BinanceClient(Client):
    def _create_futures_api_uri(self, path, version=1):
        options = {1: self.FUTURES_API_VERSION, 2: self.FUTURES_API_VERSION2}
        return self.FUTURES_URL + '/' + options[version] + '/' + path

    def _request_futures_api(self, method, path, signed=False, version=1, **kwargs):
        uri = self._create_futures_api_uri(path, version=version)

        return self._request(method, uri, signed, True, **kwargs)

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

    def futures_position_information(self, **params):
        return self._request_futures_api('get', 'positionRisk', True, version=2, data=params)

    def bulk_future_create_orders(self, coin_type, **kwargs):
        if coin_type:
            return self._request_futures_coin_api('post', "batchOrders", True, data=kwargs)
        return self._request_futures_api('post', 'batchOrders', True, data=kwargs)

    def bulk_future_cancel_orders(self, coin_type, **kwargs):
        print(kwargs)
        if coin_type:
            return self._request_futures_coin_api('delete', "batchOrders", True, data=kwargs)
        return self._request_futures_api('delete', 'batchOrders', True, data=kwargs)


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

    async def update_price_and_decimal_places(self, symbol: str, raw=False, _type='margin', coin_type=False):
        if not raw:
            if _type == 'margin':
                func = self.client.get_exchange_info
            else:
                func = self.client.futures_coin_exchange_info if coin_type else self.client.futures_exchange_info
            exchange_info = func()
            result = process_places(exchange_info, symbol)
            if result:
                self.price_places = result["price_places"]
                self.decimal_places = result["places"]
                self.difference = result["difference"]
                self.step_size = result["stepSize"]
                self.minimum = result["minimum"] + (self.step_size * 2)
                self.contract_size = result.get("contractSize")
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

    async def transfer_from_spot_to_margin(self, asset: str, amount: float, symbol: str):
        self.client.transfer_spot_to_isolated_margin(
            asset=asset, symbol=symbol, amount=amount
        )

    async def transfer_from_margin_to_spot(self, asset: str, amount: float, symbol: str):
        self.client.transfer_isolated_margin_to_spot(
            asset=asset, symbol=symbol, amount=amount
        )

    async def get_funding_account_balance(self, asset=None):
        if asset:
            result = self.client.get_asset_balance(asset)
            return BinanceBalanceType(result)
        result = self.client.get_account()
        return [BinanceBalanceType(x) for x in result['balances']]

    async def get_spot_account_balance(self, asset: str = None):
        return await self.get_funding_account_balance(asset)

    async def spot_market_order(self, symbol: str, amount: float, side: str):
        await self.update_price_and_decimal_places(symbol)
        if side == 'buy':
            self.client.order_market_buy(symbol=symbol, quantity=float(self.decimal_places % amount))
        else:
            self.client.order_market_sell(symbol=symbol, quantity=float(self.decimal_places % amount))

    async def get_futures_position(self, symbol: str = None) -> BinanceFuturePosition:
        coin_type = len(symbol.lower().split('usd_perp')) > 1
        func = self.client.futures_coin_position_information if coin_type else self.client.futures_position_information
        if symbol:
            kwargs = {}
            if coin_type:
                kwargs['marginAsset'] = symbol.lower().split("usd")[0]
            else:
                kwargs['symbol'] = symbol
            positions = func(**kwargs)
            positions = [x for x in positions if x['symbol'].lower() == symbol.lower()]
        else:
            positions = func()
        return [BinanceFuturePosition(x, coin_type) for x in positions]

    async def get_future_contracts(self):
        usdt, coin = await asyncio.gather(self.client_helper('futures_account'), self.client_helper('futures_coin_account'))
        usdt = [x for x in usdt['positions']]
        coin = [x for x in coin['positions']]
        perpetual_usdt = [x for x in usdt if len(x['symbol'].lower().split("_")) == 1]
        perpetual_coin = [x for x in coin if len(x['symbol'].lower().split('usd_perp')) > 1]
        result = [
            {'symbol': x['symbol'], 'underlying':x['symbol'].split("_")[0], 'currency':'usdt', 'leverage':x['leverage']} for x in perpetual_usdt
        ] + [
            {'symbol': x['symbol'], 'underlying':x['symbol'].split("_")[0], 'leverage':x['leverage'], 'currency':x['symbol'].lower().split("usd_")[0]} for x in perpetual_coin
        ]
        symbols = list(set([x['symbol'] for x in result]))
        r = []
        for i in symbols:
            uu = [x for x in result if x['symbol'] == i][0]
            r.append(uu)
        return r

    async def set_futures_leverage(self, symbol: str, value: float):
        coin_type = len(symbol.lower().split('usd_perp')) > 1
        func = self.client.futures_coin_change_leverage if coin_type else self.client.futures_change_leverage
        result = func(symbol=symbol, leverage=value)

    async def create_future_order(self, symbol: str, side: str, quantity: float, price: float, notional: float, raw=False, **kwargs):
        coin_type = len(symbol.lower().split('usd_perp')) > 1
        await self.update_price_and_decimal_places(symbol, raw=raw, _type="future", coin_type=coin_type)
        v = {
            "symbol": symbol.upper(),
            "price": float(self.price_places % price),
            "quantity": float(self.decimal_places % quantity),
            "side": side.upper(),
            "type": "LIMIT",
            "positionSide": kwargs.get('kind').upper(),
            "timeInForce": "GTC",
        }
        if kwargs.get("stop"):
            v["type"] = (kwargs.get("type") or "STOP").upper()
            v["workingType"] = "CONTRACT_PRICE"
            if kwargs.get("is_market"):
                v["stopPrice"] = v["price"]
                del v["price"]
                del v["timeInForce"]
                v["type"] = f"{v['type']}_MARKET".upper()
            else:
                v["stopPrice"] = float(self.price_places % kwargs["stop"])
        if kwargs.get("force_market"):
            del v["price"]
            del v["timeInForce"]
            v["type"] = "MARKET"
        if raw:
            return v
        func = (
            self.client.futures_coin_create_order
            if coin_type
            else self.client.futures_create_order
        )
        func(**v)

    async def bulk_create_future_orders(self, symbol: str, orders: typing.List[typing.Any]):
        coin_type = len(symbol.lower().split('usd_perp')) > 1
        _orders = await asyncio.gather(*[self.create_future_order(**{'raw': True, 'symbol': symbol, **x}) for x in orders])
        batches = [x for x in utils.chunks(_orders, 5)]
        result = await asyncio.gather(*[self.client_helper('bulk_future_create_orders', coin_type, batchOrders=x) for x in batches])
        return result

    async def cancel_future_order(self, symbol: str, order_id):
        coin_type = len(symbol.lower().split('usd_perp')) > 1
        func = (
            self.client.futures_coin_cancel_order
            if coin_type else self.client.futures_cancel_order
        )
        func(symbol=symbol.upper(), orderId=order_id)

    async def bulk_cancel_future_orders(self, symbol: str, order_ids: typing.List[typing.Any]):
        # coin_type = len(symbol.lower().split('usd_perp')) > 1
        await asyncio.gather(*[self.cancel_future_order(symbol, x) for x in order_ids])
        # batches = [x for x in utils.chunks(order_ids, 5)]
        # result = await asyncio.gather(*[self.client_helper('bulk_future_cancel_orders', coin_type, symbol=symbol.upper(), orderIdList=x) for x in batches])
        # return result

    async def cancel_future_open_orders(self, symbol: str):
        coin_type = len(symbol.lower().split('usd_perp')) > 1
        func = (
            self.client.futures_coin_cancel_all_open_orders
            if coin_type
            else self.client.futures_cancel_all_open_orders
        )
        func(symbol=symbol.upper())

    async def get_future_open_orders(self, symbol: str):
        coin_type = len(symbol.lower().split('usd_perp')) > 1
        func = (
            self.client.futures_coin_get_open_orders
            if coin_type else self.client.futures_get_open_orders
        )
        orders = func(symbol=symbol.upper())
        return [x for x in orders if x.get("status") != "FILLED"]
