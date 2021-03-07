import asyncio
import typing
from .types import AssetBalance, MarginAccount, LoanInfo, FuturePosition
from .utils import logger


async def loop_helper(callback):
    loop = asyncio.get_event_loop()
    future = loop.run_in_executor(None, callback)
    return await future


class BaseExchange:
    def __init__(self, api_key: str, api_secret: str, **kwargs) -> None:
        self.api_key = api_key
        self.api_secret = api_secret

    async def get_client(self) -> typing.Any:
        return await loop_helper(lambda: self.client)

    async def client_helper(self, function_name, *args, **kwargs):
        client = await self.get_client()
        return await loop_helper(
            lambda: getattr(client, function_name)(*args, **kwargs)
        )

    async def get_margin_accounts(self, symbol=None) -> typing.List[MarginAccount]:
        raise NotImplemented

    async def get_loanable_amount(self, symbol: str) -> typing.List[LoanInfo]:
        raise NotImplemented

    async def borrow_loan(self, asset: str, symbol: str, amount: float) -> bool:
        raise NotImplemented

    async def repay_loan(self, asset: str, symbol: str, amount: float) -> bool:
        raise NotImplemented

    async def create_single_order(self, symbol: str, side: str, quantity: float = None, price: float = None, notional: float = None, **kwargs):
        raise NotImplemented

    async def bulk_create_orders(self, symbol: str, orders: typing.List[typing.Any]):
        raise NotImplemented

    async def cancel_single_order(self, symbol: str, order_id):
        raise NotImplemented

    async def bulk_cancel_orders(self, symbol: str, order_ids: typing.List[typing.Any]):
        raise NotImplemented

    async def cancel_open_orders(self, symbol: str):
        raise NotImplemented

    async def get_open_orders(self, symbol: str):
        raise NotImplemented

    async def get_closed_orders(self, symbol: str):
        raise NotImplemented

    async def transfer_funds_to_trading_account(self, asset: str, amount: float = None, symbol: str = None):
        _amount = amount
        if not _amount:
            instance = await self.get_funding_account_balance(asset)
            _amount = instance.available
        await self.transfer_from_spot_to_margin(asset, _amount, symbol)

    async def transfer_funds_to_funding_account(self, asset: str, amount: float = None, symbol: str = None):
        _amount = amount
        if not _amount:
            account = await self.get_margin_accounts(symbol)
            _amount = account.balance[asset.upper()].free
        return await self.transfer_from_margin_to_spot(asset, _amount, symbol)

    async def get_funding_account_balance(self, asset=None):
        raise NotImplemented

    async def transfer_funds_to_spot_account(self, asset: str, amount: float, symbol: str):
        raise NotImplemented

    async def transfer_from_spot_to_margin(self, asset: str, amount: float, symbol: str):
        raise NotImplemented

    async def transfer_from_margin_to_spot(self, asset: str, amount: float, symbol: str):
        raise NotImplemented

    async def purchase_from_spot_and_transfer_to_margin(self, asset: str, amount: float, spot_symbol: str, side: str, margin_symbol: str):
        spot_instance = await self.get_spot_account_balance(asset)
        if spot_instance.available < amount:
            await self.spot_market_order(spot_symbol, amount, side)
            spot_instance = await self.get_spot_account_balance(asset)
        await self.transfer_from_spot_to_margin(asset, spot_instance.available, margin_symbol)

    async def get_spot_account_balance(self, asset: str = None):
        raise NotImplemented

    async def get_futures_account_balance(self, symbol: str = None):
        raise NotImplemented

    async def get_margin_account_balance(self, asset: str = None, symbol: str = None):
        raise NotImplemented

    async def transfer_from_spot_to_future(self, asset: str, amount: float, symbol: str):
        raise NotImplemented

    async def transfer_funds_to_future_account(self, asset: str, amount: float, symbol: str):
        raise NotImplemented

    async def spot_market_order(self, symbol: str, amount: float, side: str):
        raise NotImplemented

    # Futures api implementation
    async def get_futures_position(self) -> FuturePosition:
        raise NotImplemented

    async def get_future_contracts(self):
        raise NotImplemented

    async def get_futures_leverage(self, symbol: str):
        raise NotImplemented

    async def set_futures_leverage(self, symbol: str, value: float):
        raise NotImplemented

    async def create_future_order(self, symbol: str, side: str, quantity: float = None, price: float = None, notional: float = None, **kwargs):
        raise NotImplemented

    async def bulk_create_future_orders(self, symbol: str, orders: typing.List[typing.Any]):
        raise NotImplemented

    async def cancel_future_order(self, symbol: str, order_id):
        raise NotImplemented

    async def bulk_cancel_future_orders(self, symbol: str, order_ids: typing.List[typing.Any]):
        raise NotImplemented

    async def cancel_future_open_orders(self, symbol: str):
        raise NotImplemented

    async def get_future_open_orders(self, symbol: str):
        raise NotImplemented
