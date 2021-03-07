import asyncio
import typing

from okcoin import account_api as account
from okcoin import lever_api as lever
from okcoin import spot_api as spot
from okex import (account_api, futures_api, index_api, information_api,
                  lever_api, option_api, spot_api, swap_api, system_api)

from . import types, utils
from .base import BaseExchange


class OkCoinClient:
    def __init__(self, api_key: str, api_secret: str, passphrase: str, is_debug=False):
        self.api_key = api_key
        self.api_secret = api_secret
        self.passphrase = passphrase
        self.is_debug = is_debug
        self.account_api = account.AccountAPI(
            self.api_key, self.api_secret, self.passphrase, False
        )
        self.spot_api = spot.SpotAPI(
            self.api_key, self.api_secret, self.passphrase, False
        )
        self.margin_api = lever.LeverAPI(
            self.api_key, self.api_secret, self.passphrase, False
        )

    def bulk_take_orders(self, params):
        return self.margin_api.take_orders(params)

    def bulk_revoke_orders(self, params):
        return self.margin_api.revoke_orders(params)


class OkexClient(OkCoinClient):
    def __init__(self, api_key: str, api_secret: str, passphrase: str, is_debug=False):
        super().__init__(api_key, api_secret, passphrase, is_debug=is_debug)
        self.account_api = account_api.AccountAPI(self.api_key, self.api_secret, self.passphrase, False)
        self.spot_api = spot_api.SpotAPI(self.api_key, self.api_secret, self.passphrase, False)
        self.margin_api = lever_api.LeverAPI(self.api_key, self.api_secret, self.passphrase, False)
        self.futures_api = futures_api.FutureAPI(self.api_key, self.api_secret, self.passphrase, False)
        self.swap_api = swap_api.SwapAPI(self.api_key, self.api_secret, self.passphrase, False)
        self.options_api = option_api.OptionAPI(self.api_key, self.api_secret, self.passphrase, False)
        self.information_api = information_api.InformationAPI(self.api_key, self.api_secret, self.passphrase, False)
        self.index_api = index_api.IndexAPI(self.api_key, self.api_secret, self.passphrase, False)

    def bulk_future_take_orders(self, instrument_id, params):
        return self.swap_api.take_orders(instrument_id, params)

    def bulk_future_revoke_orders(self, instrument_id, params):
        return self.swap_api.revoke_orders(instrument_id, params)


class OkexAssetBalance(types.AssetBalance):
    def __init__(self, x) -> None:
        self.free = float(x['balance'])
        self.borrowed = float(x['borrowed']) + float(x['lending_fee'])
        self.total = float(x['available'])


def get_base_and_quote_info(x):
    keys = list(x.keys())
    base_asset = x[keys[0]]
    quote_asset = x[keys[1]]
    return {
        'base': keys[0].replace("currency:", ""),
        'quote': keys[1].replace("currency:", ""),
        'base_data': base_asset,
        'quote_data': quote_asset
    }


class OkexMarginAccount(types.MarginAccount):
    def __init__(self, **x) -> None:
        result = get_base_and_quote_info(x)
        self.base_asset = result['base']
        self.quote_asset = result['quote']
        self.symbol = x['instrument_id']
        self.base_asset_balance = OkexAssetBalance(result['base_data'])
        self.quote_asset_balance = OkexAssetBalance(result['quote_data'])
        self.liquidation_price = float(x['liquidation_price'])
        self.margin_ratio = float(x['margin_ratio'] or '0')
        self.balance = {self.quote_asset: self.quote_asset_balance, self.base_asset: self.base_asset_balance}


class OkexLoanInfo(types.LoanInfo):
    def __init__(self, asset, data) -> None:
        self.asset = asset
        self.rate = float(data['rate'])
        self.available = float(data['available'])


class OkexBalanceType(types.BalanceType):
    def __init__(self, x) -> None:
        self.asset = x['currency']
        self.balance = float(x['balance'])
        self.available = float(x['available'])
        self.locked = float(x['hold'])


class OkexFutureBalanceType(types.BalanceType):
    def __init__(self, x) -> None:
        self.asset = x['currency']
        self.balance = float(x['total_avail_balance'])
        self.available = float(x['max_withdraw'])
        self.locked = float(x['maint_margin_ratio'])


class OkexFuturePosition(types.FuturePosition):
    def __init__(self, x) -> None:
        self.symbol = x['instrument_id']
        coin_type = len(self.symbol.lower().split("_usd_")) > 1
        self.future_type = 'coin' if coin_type else 'usdt'
        self.size = float(x['avail_position'])
        self.entry = float(x['avg_cost'])
        self.pnl = float(x['unrealized_pnl'])
        self.liquidation_price = float(x['liquidation_price'])
        self.leverage = float(x['leverage'])
        self.margin_type = 'cross'
        self.kind = x['side']
        self.mark_price = float(x['last'])


class OKCoinExchange(BaseExchange):
    def __init__(self, **kwargs) -> None:
        self.passphrase = kwargs.get("passphrase", None)
        super().__init__(**kwargs)

    @property
    def client(self) -> OkCoinClient:
        return OkCoinClient(
            api_key=self.api_key, api_secret=self.api_secret, passphrase=self.passphrase
        )

    async def update_price_and_decimal_places(self, symbol: str, raw=False):
        if not raw:
            exchange_info = self.client.spot_api.get_coin_info()
            result = process_places(exchange_info, symbol)
            if result:
                self.price_places = result["price_places"]
                self.decimal_places = result["places"]
                self.difference = result["difference"]
                self.step_size = result["stepSize"]
                self.minimum = result["minimum"] + (self.step_size * 2)
                self.updated = True

    async def get_margin_accounts(self, symbol: str = None) -> typing.Union[typing.List[types.MarginAccount], types.MarginAccount]:
        if symbol:
            _account = self.client.margin_api.get_specific_account(symbol)
            return OkexMarginAccount(**{**_account, 'instrument_id': symbol})
        else:
            account = self.client.margin_api.get_account_info()
            return [OkexMarginAccount(**x) for x in account]

    async def get_loanable_amount(self, symbol: str) -> typing.List[types.LoanInfo]:
        result = self.client.margin_api.get_specific_config_info(symbol)
        if len(result) > 0:
            x = get_base_and_quote_info(result[0])
            return [OkexLoanInfo(x['base'], x['base_data']), OkexLoanInfo(x['quote'], x['quote_data'])]
        return []

    async def borrow_loan(self, asset: str, symbol: str, amount: float) -> bool:
        result = self.client.margin_api.borrow_coin(symbol, "", asset, amount)
        return result['result']

    async def repay_loan(self, asset: str, symbol: str, amount: float) -> bool:
        result = self.client.margin_api.repayment_coin(symbol, asset, amount)
        return result['result']

    async def create_single_order(self, symbol: str, side: str, quantity: float, price: float, notional: float = None, raw=False, **kwargs):
        await self.update_price_and_decimal_places(symbol, raw=raw)
        v = {
            'instrument_id': symbol,
            'price': float(self.price_places % price),
            'size': float(self.decimal_places % quantity) if quantity else '',
            'margin_trading': '2',
            'side': side,
            'type': 'limit',
            'order_type': "0"
        }
        if kwargs.get('is_market'):
            v['type'] = 'market'
            del v['price']
            if side.lower() == 'buy' and notional:
                v['notional'] = notional
        if raw:
            return v
        result = self.client.margin_api.take_order(**v)
        if result['result']:
            return result['order_id']

    async def bulk_create_orders(self, symbol: str, orders: typing.List[typing.Any]):
        await self.update_price_and_decimal_places(symbol)
        _orders = await asyncio.gather(*[self.create_single_order(**{'raw': True, 'symbol': symbol, **x}) for x in orders])
        batches = [x for x in utils.chunks(_orders, 10)]
        result = await asyncio.gather(*[self.client_helper('bulk_take_orders', x) for x in batches])
        return result

    async def cancel_single_order(self, symbol: str, order_id):
        self.client.margin_api.revoke_order(symbol, order_id=order_id)

    async def bulk_cancel_orders(self, symbol: str, order_ids: typing.List[typing.Any]):
        batches = [x for x in utils.chunks(order_ids, 10)]
        result = await asyncio.gather(*[self.client_helper('bulk_revoke_orders', [dict(instrument_id=symbol, order_ids=x)]) for x in batches])
        return result

    async def cancel_open_orders(self, symbol: str):
        orders = await self.get_open_orders(symbol)
        orders = [x['order_id'] for x in orders]
        await self.bulk_cancel_orders(symbol, orders)

    async def get_open_orders(self, symbol: str):
        result, cursor = self.client.margin_api.get_order_pending(symbol)
        while cursor:
            new_result, cursor = self.client.margin_api.get_order_pending(symbol, **cursor)
            result.extend(new_result)
        return result

    async def get_closed_orders(self, symbol: str):
        result, cursor = self.client.margin_api.get_order_list(symbol, "2")
        while cursor:
            new_result, cursor = self.client.margin_api.get_order_list(symbol, "2", **cursor)
            result.extend(new_result)
        return result

    async def transfer_funds_to_trading_account(self, asset: str, amount: float = None, symbol: str = None):
        _amount = amount
        if not _amount:
            account = await self.get_funding_account_balance(asset)
            _amount = account.available
        return self.client.account_api.coin_transfer(asset, _amount, '6', '5', instrument_id=symbol)

    async def transfer_funds_to_funding_account(self, asset: str, amount: float = None, symbol: str = None):
        _amount = amount
        if not _amount:
            account = await self.get_margin_accounts(symbol)
            _amount = account.balance[asset.upper()].free
        return self.client.account_api.coin_transfer(asset, _amount, '5', '6', instrument_id=symbol)

    async def get_funding_account_balance(self, asset: str = None):
        if asset:
            result = self.client.account_api.get_currency(asset)
            return OkexBalanceType(result[0])
        result = self.client.account_api.get_wallet()
        return [OkexBalanceType(x) for x in result]

    async def get_spot_account_balance(self, asset: str = None):
        if asset:
            result = self.client.spot_api.get_coin_account_info(asset)
            return OkexBalanceType(result)
        result = self.client.spot_api.get_account_info()
        return [OkexBalanceType(x) for x in result]

    async def transfer_funds_to_spot_account(self, asset: str, amount: float, symbol: str):
        return self.client.account_api.coin_transfer(asset, amount, '6', '1', instrument_id=symbol)

    async def transfer_from_spot_to_margin(self, asset: str, amount: float, symbol: str):
        return self.client.account_api.coin_transfer(asset, amount, '1', '5', instrument_id=symbol)

    async def transfer_from_margin_to_spot(self, asset: str, amount: float, symbol: str):
        return self.client.account_api.coin_transfer(asset, amount, '5', '1', instrument_id=symbol)

    async def spot_market_order(self, symbol: str, amount: float, side: str):
        self.client.spot_api.take_order(symbol, side, type='market', size=amount, notional=amount)

    async def get_margin_account_balance(self, symbol: str):
        result = await self.get_margin_accounts(symbol)
        return result.balance


def process_places(exchange_info, symbol: str):
    result = [x for x in exchange_info if x['instrument_id'].lower() == symbol.lower()]
    if result:
        result = result[0]
        def get_place(x): return abs(int(format(float(x), ".8e").split("e")[1]))
        price_places = get_place(result['tick_size'])
        quantity_places = get_place(result['size_increment'])
        return {
            "price_places": f"%.{price_places}f",
            "places": f"%.{quantity_places}f",
            "difference": 1 * 10 ** -price_places,
            "stepSize": float(result['size_increment']),
            'minimum': float(result['min_size']),
            "contractSize": result.get("contractSize"),
        }


class OkexExchange(OKCoinExchange):
    @property
    def client(self) -> OkexClient:
        return OkexClient(api_key=self.api_key, api_secret=self.api_secret, passphrase=self.passphrase)

    async def get_futures_position(self, symbol: str = None) -> OkexFuturePosition:
        # if symbol:
        #     positions = self.client.futures_api.get_specific_position(symbol)
        # else:
        if symbol:
            position = self.client.swap_api.get_specific_position(symbol)
            positions = position['holding']
        else:
            position = self.client.swap_api.get_position()
            positions = [x for y in position for x in y['holding']]
        return [OkexFuturePosition(x) for x in positions]

    async def get_future_contracts(self):
        accounts = self.client.swap_api.get_accounts()
        return [{'symbol': x['instrument_id'], 'underlying':x['underlying'], 'currency':x['currency']} for x in accounts['info']]

    async def get_futures_leverage(self, symbol: str):
        result = self.client.swap_api.get_settings(symbol)
        return result

    async def set_futures_leverage(self, symbol: str, value: float):
        result = self.client.swap_api.set_leverage(symbol, value, '3')
        return result

    async def create_future_order(self, symbol: str, side: str, quantity: float, price: float, raw=False, **kwargs):
        if kwargs['kind'].lower() == 'long':
            type = "1" if side.lower() == 'buy' else '3'
        else:
            type = '2' if side.lower() == 'sell' else '4'
        v = {
            "price": price,
            "size": quantity,
            "type": type,
        }
        if raw:
            return v
        self.client.swap_api.take_order(symbol, type, price, quantity)

    async def bulk_create_future_orders(self, symbol: str, orders: typing.List[typing.Any]):
        _orders = await asyncio.gather(*[self.create_future_order(**{'raw': True, 'symbol': symbol, **x}) for x in orders])
        batches = [x for x in utils.chunks(_orders, 10)]
        result = await asyncio.gather(*[self.client_helper('bulk_future_take_orders', symbol, x) for x in batches])
        return result

    async def cancel_future_order(self, symbol: str, order_id):
        self.client.swap_api.revoke_order(symbol, order_id=order_id)

    async def bulk_cancel_future_orders(self, symbol: str, order_ids: typing.List[typing.Any]):
        batches = [x for x in utils.chunks(order_ids, 10)]
        result = await asyncio.gather(*[self.client_helper('bulk_future_revoke_orders', symbol, x) for x in batches])
        return result

    async def cancel_future_open_orders(self, symbol: str):
        orders = await self.get_future_open_orders(symbol)
        orders = [x['order_id'] for x in orders]
        await self.bulk_cancel_future_orders(symbol, orders)

    async def get_future_open_orders(self, symbol: str):
        result, cursor = self.client.swap_api.get_order_list(symbol, '0')
        result = result['order_info']
        while cursor:
            new_result, cursor = self.client.swap_api.get_order_list(symbol, '0', **cursor)
            result.extend(new_result['order_info'])
        return result

    async def get_futures_account_balance(self, symbol: str):
        result = self.client.swap_api.get_coin_account(symbol)
        return OkexFutureBalanceType(result['info'])

    async def transfer_from_spot_to_future(self, asset: str, amount: float, symbol: str):
        return self.client.account_api.coin_transfer(asset, amount, '1', '9', instrument_id=symbol)

    async def transfer_from_margin_to_future(self, asset: str, amount: float, margin_symbol: str, future_symbol: str):
        return self.client.account_api.coin_transfer(asset, amount, '5', '9', instrument_id=margin_symbol, to_instrument_id=future_symbol)

    async def transfer_from_future_to_margin(self, asset: str, amount: float, margin_symbol: str, future_symbol):
        return self.client.account_api.coin_transfer(asset, amount, '9', '5', instrument_id=future_symbol, to_instrument_id=margin_symbol)

    async def transfer_funds_to_future_account(self, asset: str, amount: float, symbol: str):
        return self.client.account_api.coin_transfer(asset, amount, '6', '9', instrument_id=symbol)
