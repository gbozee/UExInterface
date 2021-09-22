import os

from u_exchanges import BinanceExchange, OKCoinExchange, OkexExchange,OkexV5Exchange

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

okex_v5 = OkexV5Exchange(
    api_key=os.getenv('OKEX_API_KEY'),
    api_secret=os.getenv('OKEX_API_SECRET'),
    passphrase=os.getenv('OKEX_PASSPHRASE')
)