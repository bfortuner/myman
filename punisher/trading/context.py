import os
import time
from enum import Enum, unique
import logging

import punisher.config as proj_cfg
import punisher.constants as c

from punisher.data.store import DATA_STORES, FILE_STORE
from punisher.data.feed import EXCHANGE_FEED, CSV_FEED
from punisher.data.feed import load_feed
from punisher.data.provider import PaperExchangeDataProvider
from punisher.utils.dates import Timeframe

from punisher.portfolio.portfolio import Portfolio
from punisher.portfolio.asset import Asset
from punisher.portfolio.balance import Balance, BalanceType
from punisher.portfolio.performance import PerformanceTracker

from punisher.trading import order_manager
from punisher.trading.record import Record
from punisher.exchanges.exchange import load_exchange, CCXTExchange

from punisher.utils.dates import str_to_date
from punisher.utils.logger import get_logger


class TradingMode(Enum):
    BACKTEST = 'backtest'
    SIMULATION = 'simulation'
    LIVE = 'live'


class Context():
    def __init__(self, exchange, feed, record, config):
        self.exchange = exchange
        self.feed = feed
        self.record = record
        self.config = config
        self.logger = get_logger(fpath=os.path.join(
            proj_cfg.DATA_DIR, config['experiment']),
            logger_name='progress',
            ch_log_level=logging.INFO)

    @classmethod
    def from_config(self, cfg):
        assert cfg is not None
        root = os.path.join(proj_cfg.DATA_DIR, cfg['experiment'])
        store = DATA_STORES[cfg['store']](
            root=root)
        feed = load_feed(
            name=cfg['feed']['name'],
            fpath=cfg['feed']['fpath'],
            assets=[Asset.from_symbol(a) for a in cfg['feed']['symbols']],
            timeframe=Timeframe[cfg['feed']['timeframe']],
            start=str_to_date(cfg['feed'].get('start')),
            end=str_to_date(cfg['feed'].get('end')),
        )
        perf = PerformanceTracker(
            starting_cash=cfg['starting_cash'],
            timeframe=Timeframe[cfg['feed']['timeframe']],
            store=store
        )
        record = Record(
            config=cfg,
            portfolio=Portfolio(cfg['starting_cash'], perf),
            balance=Balance.from_dict(cfg['balance']),
            store=store
        )

        # Hack to create the PaperExchangeDataProvider here as our default
        # data provider for the Paper exchange using the feed provided

        if cfg['exchange'].get('data_provider') == None:
            cfg['exchange']['data_provider']: PaperExchangeDataProvider(feed)

        cfg['exchange']['balance']: cfg['balance']

        exchange = load_exchange(
            cfg['exchange']['exchange_id'],
            cfg=cfg['exchange']
        )

        # TODO: Maybe make exchange initialize a feed instead
        feed.initialize(exchange)

        return Context(
            config=cfg,
            exchange=exchange,
            feed=feed,
            record=record
        )


def default_config(trading_mode):
    """
    Method to get sensible defaults for each trading mode.
    Can be used by users as a set of base configs to work with.
    Returns config dictionary
    """

    default_cfg_template = {
        'experiment': 'default',
        'cash_asset': c.BTC,
        'starting_cash': 1.0,
        'store': FILE_STORE,
        'balance': c.DEFAULT_BALANCE,
        'feed': {
            'fpath': os.path.join(proj_cfg.DATA_DIR, c.DEFAULT_FEED_CSV_FILENAME),
            'symbols': ['ETH/BTC'],
            'timeframe': Timeframe.THIRTY_MIN.name,
        },
        'exchange': {}
    }

    if trading_mode == TradingMode.BACKTEST:
        default_cfg_template['feed']['name'] = CSV_FEED
        default_cfg_template['feed']['start'] = '2018-01-01T00:00:00'
        default_cfg_template["exchange"]['exchange_id'] = c.PAPER
        return default_cfg_template

    elif trading_mode == TradingMode.SIMULATION:
        default_cfg_template['feed']['name'] = EXCHANGE_FEED
        default_cfg_template['exchange']['exchange_id'] = c.PAPER
        default_cfg_template['exchange']['data_provider'] = CCXTExchange(
            c.DEFAULT_DATA_PROVIDER_EXCHANGE, {})
        return default_cfg_template

    else:
        print("No default config for {} trading mode".format(trading_mode))
        exit(1)