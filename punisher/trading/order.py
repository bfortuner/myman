import copy
import json
import uuid
from datetime import datetime
from enum import Enum, unique

from punisher.portfolio.asset import Asset
from punisher.utils.dates import str_to_date, date_to_str
from punisher.trading.coins import get_symbol
from punisher.utils.encoders import EnumEncoder


@unique
class OrderStatus(Enum):
    CREATED = "Order not yet submitted to exchange"
    OPEN = "Order successfully created on exchange"
    FILLED = "Order completely filled on exchange"
    CLOSED = "Order closed/filled by exchange" # ccxt returns this ???
    CANCELED = "Order canceled by user"
    FAILED = "Order failed/rejected by exchange. Will retry"
    KILLED = "Order rejected by exchange. Will not retry"

    def __repr__(self):
        return str(self.name)


@unique
class OrderType(Enum):
    LIMIT_BUY = {'type':'limit', 'side':'buy', 'desc':''}
    LIMIT_SELL = {'type':'limit', 'side':'sell', 'desc':''}
    MARKET_BUY = {'type':'market', 'side':'buy', 'desc':''}
    MARKET_SELL = {'type':'market', 'side':'sell', 'desc':''}
    STOP_LIMIT_BUY = 4
    STOP_LIMIT_SELL = 5

    @classmethod
    def from_type_side(self, type_, side):
        # TODO: Add more order types
        order_type_map = {
            'limit_buy': OrderType.LIMIT_BUY,
            'limit_sell': OrderType.LIMIT_SELL,
            'market_buy': OrderType.MARKET_BUY,
            'market_sell': OrderType.MARKET_SELL,
        }
        key = type_.lower() + '_' + side.lower()
        return order_type_map[key]

    @classmethod
    def buy_types(self):
        return set([
            OrderType.LIMIT_BUY,
            OrderType.MARKET_BUY,
            OrderType.STOP_LIMIT_BUY
        ])

    @classmethod
    def sell_types(self):
        return set([
            OrderType.LIMIT_SELL,
            OrderType.MARKET_SELL,
            OrderType.STOP_LIMIT_SELL
        ])

    @property
    def type(self):
        return self.value['type']

    @property
    def side(self):
        return self.value['side']

    def is_buy(self):
        return self in self.buy_types()

    def is_sell(self):
        return self in self.sell_types()

    def __repr__(self):
        return str(self.name)


class Order():
    __slots__ = [
        "id", "exchange_id", "exchange_order_id", "asset", "price",
        "quantity", "filled_quantity", "order_type", "status", "created_time",
        "opened_time", "filled_time", "canceled_time", "fee", "retries", "cost"
    ]

    def __init__(self, exchange_id, asset, price, quantity,
                 order_type, exchange_order_id=None):
        self.id = self.make_id()
        self.exchange_id = exchange_id
        self.exchange_order_id = exchange_order_id
        self.asset = asset
        self.price = price
        self.quantity = quantity # e.g. # of bitcoins
        self.cost = 0.0
        self.filled_quantity = 0.0
        self.order_type = self.set_order_type(order_type)
        self.status = OrderStatus.CREATED
        self.created_time = datetime.utcnow()
        self.opened_time = None
        self.filled_time = None
        self.canceled_time = None
        self.fee = {}
        self.retries = 0

    @classmethod
    def make_id(self):
        return uuid.uuid4().hex

    def set_order_type(self, order_type):
        assert order_type in OrderType
        self.order_type = order_type
        return self.order_type

    def set_status(self, status):
        assert status in OrderStatus
        self.status = status

    def to_dict(self):
        d = {
            name: getattr(self, name)
            for name in self.__slots__
        }
        del d['asset']
        d['symbol'] = self.asset.symbol
        d['status'] = self.status.name
        d['order_type'] = self.order_type.name
        d['created_time'] = date_to_str(self.created_time)
        d['opened_time'] = date_to_str(self.opened_time)
        d['filled_time'] = date_to_str(self.filled_time)
        d['canceled_time'] = date_to_str(self.canceled_time)
        return d

    @classmethod
    def from_dict(self, order_dct):
        order = Order(
            exchange_id=order_dct['id'],
            asset=Asset.from_symbol(order_dct['symbol']),
            price=order_dct['price'],
            quantity=order_dct['amount'],
            order_type=OrderType.from_type_side(
                order_dct['type'], order_dct['side']),
            exchange_order_id=order_dct['id']
        )
        order.filled_quantity = order_dct.get('filled', 0)
        order.status = OrderStatus[
            order_dct.get('status', OrderStatus.CREATED.name).upper()]
        order.fee = order_dct.get('fee', 0.0)
        return order

    def to_json(self):
        dct = self.to_dict()
        return json.dumps(dct, cls=EnumEncoder, indent=4)

    @classmethod
    def from_json(self, json_str):
        dct = json.loads(json_str)
        return self.from_dict(dct)

    def __repr__(self):
        return self.to_json()

def buy_order_types():
    return [OrderType.LIMIT_BUY,
            OrderType.MARKET_BUY,
            OrderType.STOP_LIMIT_BUY]

def sell_order_types():
    return [OrderType.LIMIT_SELL,
            OrderType.MARKET_SELL,
            OrderType.STOP_LIMIT_SELL]
