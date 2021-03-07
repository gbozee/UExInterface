
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


class LoanInfo:
    asset: str
    rate: float
    available: float
    locked: float

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__} {self.asset} {self.available} {self.rate}>"


class BalanceType:
    balance: float
    available: float
    asset: str

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__} {self.asset} {self.balance}>"


class FuturePosition:
    symbol: str
    size: float
    entry: float
    pnl: float
    liquidation_price: float
    leverage: float
    margin_type: str
    kind: str
    mark_price: float
    future_type: str
