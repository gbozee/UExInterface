import asyncio
import typing


async def loop_helper(callback):
    loop = asyncio.get_event_loop()
    future = loop.run_in_executor(None, callback)
    return await future


class AssetBalance(object):
    borrowed: float
    free: float
    total: float

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__} total: {self.total}>"


class MarginAccount:
    base_asset: str
    quote_asset: str
    symbol: str
    base_asset_balance: AssetBalance
    quote_asset_balance: AssetBalance
    liquidation_price: float
    margin_ratio: float

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__} {self.symbol}>"


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

    async def get_margin_accounts(self) -> typing.List[MarginAccount]:
        raise NotImplemented
