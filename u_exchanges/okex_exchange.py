import asyncio
import typing

from okex.v5 import Account_api as account
from okex.v5 import Funding_api as funding
from okex.v5 import Market_api as market
from okex.v5 import Public_api as public
from okex.v5 import Trade_api as trade
from okex.v5 import subAccount_api as sub_account
from okex.v5 import status_api as status

from . import types, utils
from .base import BaseExchange


class OKEXClient:
    def __init__(self, api_key: str, api_secret: str, passphrase: str, is_debug=False):
        self.api_key = api_key
        self.api_secret = api_secret
        self.passphrase = passphrase
        self.is_debug = is_debug
        self.account_api = account.AccountAPI(
            self.api_key, self.api_secret, self.passphrase, False
        )
        flag = '1' if self.is_debug else '0'
        self.funding_api = funding.FundingAPI(
            self.api_key, self.api_secret, self.passphrase, False, flag
        )
        self.market_api = market.MarketAPI(
            self.api_key, self.api_secret, self.passphrase, False, flag
        )
        self.public_api = public.PublicAPI(
            self.api_key, self.api_secret, self.passphrase, False, flag
        )
        self.trading_api = trade.TradeAPI(
            self.api_key, self.api_secret, self.passphrase, False, flag
        )
        self.sub_account_api = sub_account.SubAccountAPI(
            self.api_key, self.api_secret, self.passphrase, False, flag
        )
        self.status_api = status.StatusAPI(
            self.api_key, self.api_secret, self.passphrase, False, flag
        )


class OkexV5Exchange(BaseExchange):
    def __init__(self, **kwargs) -> None:
        self.passphrase = kwargs.get("passphrase", None)
        self.is_debug = kwargs.get("is_debug", None)
        super().__init__(**kwargs)

    @property
    def client(self) -> OKEXClient:
        return OKEXClient(
            api_key=self.api_key,
            api_secret=self.api_secret,
            passphrase=self.passphrase,
            is_debug=self.is_debug,
        )


def process_places(exchange_info, symbol: str):
    result = [x for x in exchange_info if x["instrument_id"].lower() == symbol.lower()]
    if result:
        result = result[0]

        def get_place(x):
            return abs(int(format(float(x), ".8e").split("e")[1]))

        price_places = get_place(result["tick_size"])
        quantity_places = get_place(result["size_increment"])
        return {
            "price_places": f"%.{price_places}f",
            "places": f"%.{quantity_places}f",
            "difference": 1 * 10 ** -price_places,
            "stepSize": float(result["size_increment"]),
            "minimum": float(result["min_size"]),
            "contractSize": result.get("contractSize"),
        }
