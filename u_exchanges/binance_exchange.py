from .base import BaseExchange

from binance.exceptions import BinanceAPIException
from binance.client import Client as BinanceClient


class BinanceExchange(BaseExchange):
    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)

    @property
    def client(self)->BinanceClient:
        return BinanceClient(api_key=self.api_key, api_secret=self.api_secret)
