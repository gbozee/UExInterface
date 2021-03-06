from .base import BaseExchange
from okcoin import account_api as account, spot_api as spot, lever_api as lever


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


class OKCoinExchange(BaseExchange):
    def __init__(self, **kwargs) -> None:
        self.passphrase = kwargs.pop("passphrase",None)
        super().__init__(**kwargs)

    @property
    def client(self)->OkCoinClient:
        return OkCoinClient(
            api_key=self.api_key, api_secret=self.api_secret, passphrase=self.passphrase
        )
