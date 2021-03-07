import os

from u_exchanges import BinanceExchange, OKCoinExchange, OkexExchange

binance = BinanceExchange(
    api_key=os.getenv("BINANCE_API_KEY"), api_secret=os.getenv("BINANCE_API_SECRET")
)

okcoin = OKCoinExchange(
    api_key=os.getenv("OKCOIN_API_KEY"),
    api_secret=os.getenv("OKCOIN_API_SECRET"),
    passphrase=os.getenv("OKCOIN_PASSPHRASE"),
)

okex = OkexExchange(
    api_key=os.getenv('OKEX_API_KEY'),
    api_secret=os.getenv('OKEX_API_SECRET'),
    passphrase=os.getenv('OKEX_PASSPHRASE')
)
