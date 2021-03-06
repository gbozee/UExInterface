import asyncio
import typing
from .types import AssetBalance, MarginAccount, LoanInfo
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
