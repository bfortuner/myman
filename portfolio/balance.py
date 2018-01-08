from enum import Enum, unique

import constants as c
import config as cfg

from .asset import get_symbol

FREE = "free"
USED = "used"
TOTAL = "total"

class Balance():
    def __init__(self, cash_currency=c.BTC, starting_cash=1.0):
        self.free = {cash_currency: starting_cash}
        self.used = {cash_currency: 0.0}
        self.total = {cash_currency: 0.0}

    @property
    def currencies(self):
        return list(self.total.keys())

    def get(self, currency):
        return {
            FREE: self.free[currency],
            USED: self.used[currency],
            TOTAL: self.total[currency],
        }

    def update(self, currency, delta_free, delta_used):
        self.free[currency] += delta_free
        self.used[currency] += delta_used
        self.total[currency] = self.free[currency] + self.used[currency]

    def add_currency(self, currency):
        assert currency not in self.currencies
        self.free[currency] = 0.0
        self.used[currency] = 0.0
        self.total[currency] = 0.0

    def to_dict(self):
        dct = { c: self.get(c) for c in self.currencies }
        dct[FREE] = self.free
        dct[USED] = self.used
        dct[TOTAL] = self.total
        return dct

    @classmethod
    def from_dict(self, dict):
        self.free = balance[FREE]
        self.used = balance[USED]
        self.total = balance[TOTAL]


@unique
class BalanceType(Enum):
    FREE = "free"
    USED = "used"
    TOTAL = "total"



## Helpers

def get_total_value(balance, cash_currency, exchange_rates):
    cash_value = 0.0
    for currency in balance.currencies:
        symbol = get_symbol(currency, cash_currency)
        quantity = balance.get(currency)[TOTAL]
        rate = exchange_rates[symbol]
        cash_value += quantity * exchange_rate
    return cash_value
