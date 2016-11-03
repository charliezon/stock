import time, uuid

from orm import Model, StringField, BooleanField, FloatField, IntegerField

def next_id():
    return '%015d%s000' % (int(time.time() * 1000), uuid.uuid4().hex)

class User(Model):
    __table__ = 'users'

    id = StringField(primary_key=True, default=next_id, ddl='varchar(50)')
    email = StringField(ddl='varchar(50)')
    passwd = StringField(ddl='varchar(50)')
    admin = BooleanField()
    name = StringField(ddl='varchar(50)')
    image = StringField(ddl='varchar(500)')
    created_at = FloatField(default=time.time)

class Account(Model):
    __table__ = 'accounts'

    id = StringField(primary_key=True, default=next_id, ddl='varchar(50)')
    user_id = StringField(ddl='varchar(50)')
    name = StringField(ddl='varchar(50)')
    commission_rate = FloatField()
    initial_funding = FloatField()
    created_at = FloatField(default=time.time)

class AccountRecord(Model):
    __table__ = 'account_records'

    id = StringField(primary_key=True, default=next_id, ddl='varchar(50)')
    account_id = StringField(ddl='varchar(50)')
    market_condition = IntegerField()
    stock_position = FloatField()
    available_funding = FloatField()
    total_stock_value = FloatField()
    total_assets = FloatField()
    float_profit_lost = FloatField()
    total_profit = FloatField()
    principle = FloatField()
    created_at = FloatField(default=time.time)

class StockHoldRecord(Model):
    __table__ = 'stock_hold_records'

    id = StringField(primary_key=True, default=next_id, ddl='varchar(50)')
    account_record_id = StringField(ddl='varchar(50)')
    stock_id = StringField(ddl='varchar(50)')
    stock_amount = IntegerField()
    stock_current_price = FloatField()
    stock_buy_price = FloatField()
    stock_sell_price = FloatField()
    stock_buy_date = FloatField(default=time.time)
    created_at = FloatField(default=time.time)

class Stock(Model):
    __table__ = 'stocks'

    id = StringField(primary_key=True, default=next_id, ddl='varchar(50)')
    stock_id = StringField(ddl='varchar(50)')
    stock_name = StringField(ddl='varchar(50)')
    created_at = FloatField(default=time.time)
