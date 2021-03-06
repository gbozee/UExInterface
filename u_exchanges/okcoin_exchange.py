import typing
from .base import AssetBalance, BaseExchange, MarginAccount
from okcoin import account_api as account, spot_api as spot, lever_api as lever
from okex import account_api, spot_api, lever_api, futures_api, swap_api, option_api, information_api, index_api, system_api


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
        self.level_api = lever.LeverAPI(
            self.api_key, self.api_secret, self.passphrase, False
        )


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


class OkexAssetBalance(AssetBalance):
    def __init__(self, x) -> None:
        self.free = float(x['balance'])
        self.borrowed = float(x['borrowed']) + float(x['lending_fee'])
        self.total = float(x['available'])


class OkexMarginAccount(MarginAccount):
    def __init__(self, **x) -> None:
        keys = list(x.keys())
        base_asset = x[keys[0]]
        quote_asset = x[keys[1]]
        self.base_asset = keys[0].replace("currency:", "")
        self.quote_asset = keys[1].replace("currency:", "")
        self.symbol = x['instrument_id']
        self.base_asset_balance = OkexAssetBalance(base_asset)
        self.quote_asset_balance = OkexAssetBalance(quote_asset)
        self.liquidation_price = float(x['liquidation_price'])
        self.margin_ratio = float(x['margin_ratio'] or '0')


class OKCoinExchange(BaseExchange):
    def __init__(self, **kwargs) -> None:
        self.passphrase = kwargs.get("passphrase", None)
        super().__init__(**kwargs)

    @property
    def client(self) -> OkCoinClient:
        return OkCoinClient(
            api_key=self.api_key, api_secret=self.api_secret, passphrase=self.passphrase
        )


class OkexExchange(OKCoinExchange):
    @property
    def client(self) -> OkexClient:
        return OkexClient(api_key=self.api_key, api_secret=self.api_secret, passphrase=self.passphrase)

    async def get_margin_accounts(self) -> typing.List[MarginAccount]:
        account = self.client.margin_api.get_account_info()
        return [OkexMarginAccount(**x) for x in account]
