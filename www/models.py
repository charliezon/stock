#!/usr/bin/env python3

# -*- coding: utf-8 -*-



__author__ = 'Chaoliang Zhong'

import time, uuid, datetime

from orm import Model, StringField, BooleanField, FloatField, IntegerField

def next_id():
    return '%015d%s000' % (int(time.time() * 1000), uuid.uuid4().hex)

def today():
    return time.strftime("%Y-%m-%d", time.localtime())

def convert_date(date):
    return datetime.datetime.strptime(date,'%Y-%m-%d')

class User(Model):
    __table__ = 'users'

    id = StringField(primary_key=True, default=next_id, ddl='varchar(50)')
    email = StringField(ddl='varchar(50)')
    passwd = StringField(ddl='varchar(50)')
    admin = BooleanField()
    name = StringField(ddl='varchar(50)')
    image = StringField(ddl='varchar(500)')
    created_at = FloatField(default=time.time)

class MarketState(Model):
    __table__ = 'market_state'

    date = StringField(primary_key=True, default=today, ddl='varchar(50)')
    market_state  = IntegerField()

class Account(Model):
    __table__ = 'accounts'

    id = StringField(primary_key=True, default=next_id, ddl='varchar(50)')
    user_id = StringField(ddl='varchar(50)')
    name = StringField(ddl='varchar(50)')
    commission_rate = FloatField()
    initial_funding = FloatField()
    success_times = IntegerField(default=0)
    fail_times = IntegerField(default=0)
    created_at = FloatField(default=time.time)

class AccountRecord(Model):
    __table__ = 'account_records'

    id = StringField(primary_key=True, default=next_id, ddl='varchar(50)')
    date = StringField(default=today, ddl='varchar(50)')
    account_id = StringField(ddl='varchar(50)')
    stock_position = FloatField()
    security_funding = FloatField()
    bank_funding = FloatField()
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
    stock_code = StringField(ddl='varchar(50)')
    stock_name = StringField(ddl='varchar(50)')
    stock_amount = IntegerField()
    stock_current_price = FloatField()
    stock_buy_price = FloatField()
    stock_sell_price = FloatField()
    stock_buy_date = StringField(default=today, ddl='varchar(50)')
    created_at = FloatField(default=time.time)

class StockTradeRecord(Model):
    __table__ = 'stock_trade_records'

    id = StringField(primary_key=True, default=next_id, ddl='varchar(50)')
    account_id = StringField(ddl='varchar(50)')
    stock_code = StringField(ddl='varchar(50)')
    stock_name = StringField(ddl='varchar(50)')
    stock_amount = IntegerField()
    stock_price = FloatField()
    stock_date = StringField(default=today, ddl='varchar(50)')
    stock_operation = BooleanField()  # True: buy, False: sell
    trade_series = StringField(ddl='varchar(50)')
    created_at = FloatField(default=time.time)

class AccountAssetChange(Model):
    __table__ = 'account_asset_change'

    id = StringField(primary_key=True, default=next_id, ddl='varchar(50)')
    account_id = StringField(ddl='varchar(50)')
    change_amount = FloatField()
    operation = IntegerField()  # 0: minus, 1: add, 2: set
    security_or_bank = BooleanField()
    date = StringField(default=today, ddl='varchar(50)')
    created_at = FloatField(default=time.time)
