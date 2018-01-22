

class Asset():
    """
    Base = currency you want to trade
    Quote = currency you want the Base price displayed in

    If you place a BUY order for Base/Quote, it means you're
    buying Base and paying in Quote.

    Other future properties might include:
        * precision
        * supported_exchanges
    """

    def __init__(self, base, quote):
        self.base = base
        self.quote = quote

    @property
    def id(self):
        return get_id(self.base, self.quote)

    @property
    def symbol(self):
        return get_symbol(self.base, self.quote)

    def reverse_symbol(self):
        return self.quote + '/' + self.base

    def __eq__(self, other):
        return (self.base == other.base and self.quote == other.quote)

    def to_dict(self):
        return {
            'id': self.id,
            'symbol': self.symbol,
            'base': self.base,
            'quote': self.quote,
        }

    @classmethod
    def from_symbol(self, symbol):
        if '/' in symbol:
            base,quote = symbol.split('/')
        else:
            base = symbol[:3]
            quote = symbol[3:]
        return Asset(base, quote)

    def __eq__(self, obj):
        return obj.symbol == self.symbol


# Helpers

def get_id(base, quote):
    return base + '_' + quote

def get_symbol(base, quote):
    return base + '/' + quote
