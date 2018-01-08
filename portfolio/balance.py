import constants as c
import config as cfg
from enum import Enum, unique
from .asset import get_symbol


FREE = "free"
USED = "used"
TOTAL = "total"

class Balance():
    def __init__(self, cash_currency, starting_cash=0.0, balance=None):
        self.cash_currency = cash_currency
        self.starting_cash = starting_cash
        self.free = {}
        self.used = {}
        self.total = {}
        self.initialize(balance)

    def initialize(self, balance):
        if balance is None:
            self.free = {self.cash_currency: self.starting_cash}
            self.used = {self.cash_currency: 0.0}
            self.total = {self.cash_currency: 0.0}
        else:
            self.free = balance[FREE]
            self.used = balance[USED]
            self.total = balance[TOTAL]

    @property
    def currencies(self):
        return self.total.keys()

    def get(self, currency):
        return {
            FREE: self.free[currency],
            USED: self.used[currency],
            TOTAL: self.total[currency],
        }

    def update(self, currency, free, used):
        self.free[currency] = free
        self.used[currency] = used
        self.total = self.free[currency] + self.used[currency]


@unique
class BalanceType(Enum):
    FREE = "Quantity available for trading"
    USED = "Quantity currently invested"
    TOTAL = "Free + Used"


## Helpers

def get_total_value(balance, cash_currency, exchange_rates):
    cash_value = 0.0
    for currency in balance.currencies:
        symbol = get_symbol(currency, cash_currency)
        quantity = balance.get(currency[TOTAL])
        rate = exchange_rates[symbol]
        cash_value += quantity * exchange_rate
    return cash_value
                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                           
