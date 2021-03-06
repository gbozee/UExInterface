import typing
from .base import AssetBalance, BaseExchange, MarginAccount

from binance.exceptions import BinanceAPIException
from binance.client import Client as BinanceClient


class BinanceAssetBalance(AssetBalance):
    def __init__(self, x) -> None:
        self.free = float(x['free'])
        self.borrowed = float(x['borrowed']) + float(x['interest'])
        self.total = float(x['totalAsset'])


class BinanceMarginAccount(MarginAccount):
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


class BinanceExchange(BaseExchange):
    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)

    @property
    def client(self) -> BinanceClient:
        return BinanceClient(api_key=self.api_key, api_secret=self.api_secret)

    async def get_margin_accounts(self) -> typing.List[MarginAccount]:
        account = self.client.get_isolated_margin_account()
        return [BinanceMarginAccount(**x) for x in account['assets']]
