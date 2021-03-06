import sys
import time
import threading

import pandas as pd
import numpy as np

import punisher.config as cfg
import punisher.constants as c
from punisher.portfolio.asset import Asset
from punisher.feeds import ohlcv_feed
from punisher.trading import coins
from punisher.trading.record import Record
from punisher.utils.dates import date_to_str


class ChartDataProvider():
    def __init__(self, refresh_sec=None):
        self.refresh_sec = refresh_sec
        self.thread = None

    def initialize(self):
        if self.refresh_sec is not None:
            self.thread = threading.Thread(target=self._update)
            self.thread.start()

    def update(self):
        return NotImplemented

    def _update(self):
        while True:
            print("Refreshing data")
            self.update()
            time.sleep(self.refresh_sec)


class RecordChartDataProvider():
    def __init__(self, root_dir, refresh_sec=5, t_minus=sys.maxsize):
        self.root_dir = root_dir
        self.refresh_sec = refresh_sec
        self.t_minus = t_minus
        self.thread = threading.Thread(target=self.update)
        self.record = Record.load(self.root_dir)

    def initialize(self):
        self.thread.start()

    def get_time(self):
        return self.get_ohlcv().get('utc')

    def get_symbols(self):
        return self.record.portfolio.symbols

    def get_config(self):
        return self.record.config

    def get_ohlcv(self, cash_coin=None):
        if abs(self.t_minus) >= len(self.record.ohlcv):
            data = ohlcv_feed.OHLCVData(self.record.ohlcv.copy())
        else:
            data = ohlcv_feed.OHLCVData(
                self.record.ohlcv.iloc[-self.t_minus:].copy())
        if cash_coin is None or cash_coin == self.record.portfolio.cash_currency:
            return data
        assets = self.get_assets()
        ex_ids = self.get_exchange_ids()
        for ex_id in ex_ids:
            for asset in assets:
                for field in ['open','high','low','close']:
                    col_name = ohlcv_feed.get_col_name(field, asset.symbol, ex_id)
                    cash_value = ohlcv_feed.get_cash_value(
                        data.ohlcv_df, field, asset, ex_id, cash_coin)
                    data.ohlcv_df[col_name] = cash_value
        return data

    def get_assets(self, exchange_id=None):
        cols = ([col for col in self.record.ohlcv.columns
                 if col not in ['epoch', 'utc']])
        symbols = set()
        for col in cols:
            field,symbol,ex_id = col.split('_')
            if exchange_id is None or exchange_id == ex_id:
                symbols.add(symbol)
        return [Asset.from_symbol(sym) for sym in symbols]

    def get_exchange_ids(self):
        cols = ([col for col in self.record.ohlcv.columns
                 if col not in ['epoch', 'utc']])
        ids = set()
        for col in cols:
            field,symbol,ex_id = col.split('_')
            ids.add(ex_id)
        return list(ids)

    def get_quote_currencies(self):
        currencies = set()
        for asset in self.get_assets():
            currencies.add(asset.quote)
        return currencies

    def get_base_currencies(self):
        currencies = set()
        for asset in self.get_assets():
            currencies.add(asset.base)
        return currencies

    def get_positions(self):
        positions = self.record.portfolio.positions
        return pd.DataFrame([p.to_dict() for p in positions])

    def get_positions_dct(self):
        positions = self.record.portfolio.positions
        dct = [p.to_dict() for p in positions]
        return dct

    def get_performance(self):
        return self.record.portfolio.perf

    def get_pnl(self, quote_coin, ex_id):
        periods = self.record.portfolio.perf.periods
        cash_currency = self.record.portfolio.cash_currency
        ex_rates = ohlcv_feed.get_exchange_rate(
            self.get_ohlcv().df, cash_currency, quote_coin, ex_id)
        df = pd.DataFrame([
            [p['end_time'], p['pnl']] for p in periods
        ], columns=['utc','pnl'])
        df['pnl'] = df['pnl'] * ex_rates
        return df

    def get_returns(self, quote_coin, ex_id):
        periods = self.record.portfolio.perf.periods
        cash_currency = self.record.portfolio.cash_currency
        ex_rates = ohlcv_feed.get_exchange_rate(
            self.get_ohlcv().df, cash_currency, quote_coin, ex_id)
        start_cash = self.record.portfolio.starting_cash * ex_rates[0]
        df = pd.DataFrame([
            [p['end_time'], p['pnl']] for p in periods],
                columns=['utc','returns'])
        df['returns'] = df['returns'] * ex_rates / start_cash
        return df

    def get_balance(self):
        columns = ['coin', 'free', 'used', 'total']
        balance = self.record.balance
        dct = balance.to_dict()
        return pd.DataFrame(
            data=[
                [c, dct[c]['free'], dct[c]['used'], dct[c]['total']]
                for c in balance.currencies],
            columns=columns
        )

    def get_balance_dct(self):
        coins = self.record.balance.currencies
        dct = self.record.balance.to_dict()
        return [{
            'coin':c, 'free':dct[c]['free'],
            'used':dct[c]['used'], 'total':dct[c]['total']
        } for c in coins]

    def get_orders(self):
        columns = [
            'created', 'exchange', 'symbol', 'type',
            'price', 'quantity', 'filled', 'status'
        ]
        data = [
            [o.created_time, o.exchange_id, o.asset.symbol,
             o.order_type.name, o.price, o.quantity, o.filled_quantity,
             o.status.name] for o in self.record.orders.values()
        ]
        return pd.DataFrame(data=data, columns=columns)

    def get_orders_dct(self):
        return [{
            'created': date_to_str(o.created_time),
            'exchange': o.exchange_id,
            'symbol': o.asset.symbol,
            'type': o.order_type.name,
            'price': o.price,
            'quantity': o.quantity,
            'filled': o.filled_quantity,
            'status': o.status.name
            } for o in self.record.orders.values()
        ]

    def get_orders_hist(self):
        raise NotImplemented

    def get_metrics(self):
        return self.record.metrics

    def update(self):
        while True:
            print("Refreshing data")
            self.record = Record.load(self.root_dir)
            time.sleep(self.refresh_sec)



class OHLCVChartDataProvider(ChartDataProvider):
    def __init__(self, feed, refresh_sec=5, t_minus=sys.maxsize):
        super().__init__(refresh_sec)
        self.feed = feed
        self.t_minus = t_minus
        self.ohlcv = {}

    def initialize(self):
        super().initialize()
        self.feed.initialize()
        # Optionally include some history
        # self.ohlcv = self.feed.history(t_minus=100)

    def get_symbols(self):
        return ['ETH/BTC','LTC/BTC']

    def get_next(self):
        """
        Returns dictionary:
            {'close': 0.077,
             'high': 0.0773,
             'low': 0.0771,
             'open': 0.0772,
             'utc': Timestamp('2018-01-08 22:22:00'),
             'volume': 222.514}
        """
        return self.feed.next().to_dict()

    def get_all(self):
        """Returns Dataframe"""
        return self.feed.history()

    def update(self):
        self.feed.update()
