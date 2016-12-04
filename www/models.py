#!/usr/bin/env python3

# -*- coding: utf-8 -*-



__author__ = 'Chaoliang Zhong'

import time, uuid, datetime, math

from orm import Model, StringField, BooleanField, FloatField, IntegerField

from decimal import Decimal as D



def next_id():
    return '%015d%s000' % (int(time.time() * 1000), uuid.uuid4().hex)

def today():
    return time.strftime("%Y-%m-%d", time.localtime())

def convert_date(date):
    return datetime.datetime.strptime(date,'%Y-%m-%d')

def round_float(g, pos=2):
    if g<0:
        f = -g
    else:
        f = g
    p1 = pow(D('10'), D(str(pos+1)))
    last = D(str(int(D(str(f))*p1)))%D('10')
    p = pow(D('10'), D(str(pos)))
    if last >= 5:
        result = float(math.ceil(D(str(f))*p)/p)
    else:
        result = float(math.floor(D(str(f))*p)/p)
    if g<0:
        return -result
    else:
        return result


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

class DailyParam(Model):
    __table__ = 'daily_params'

    date = StringField(primary_key=True, default=today, ddl='varchar(50)')
    shanghai_index = FloatField() # 沪指指数
    stock_market_status = IntegerField()  # 0: 熊市, 1: 小牛市, 2: 大牛市
    twenty_days_line = BooleanField() # False: 沪指位于20日线以下, True: 沪指位于20日线以上
    increase_range = FloatField() #沪指涨幅
    three_days_average_shanghai_increase = FloatField() #沪指近3天平均涨幅
    shanghai_break_twenty_days_line = BooleanField() # False: 沪指非第一天跌破20日线, True: 沪指第一天跌破20日线
    shanghai_break_twenty_days_line_for_two_days = BooleanField() # False: 沪指非连续两天跌破20日线, True: 沪指连续两天跌破20日线（未连续3天）
    shenzhen_break_twenty_days_line = BooleanField() # False: 深指非第一天跌破20日线, True: 深指第一天跌破20日线
    shenzhen_break_twenty_days_line_for_two_days = BooleanField() # False: 深指非连续两天跌破20日线, True: 深指连续两天跌破20日线（未连续3天）
    all_stock_amount = IntegerField()  # 沪深A股+创业板总股票数
    buy_stock_amount = IntegerField()  # 沪深A股+创业板发出买入信号的股票数
    buy_stock_ratio = FloatField() # 发出买入信号的股票比例
    pursuit_stock_amount =  IntegerField()  # 沪深A股+创业板发出追涨信号的股票数
    pursuit_stock_ratio = FloatField() # 发出追涨信号的股票比例
    iron_stock_amount =  IntegerField()  # 沪深A股+创业板发出买入或追涨信号的普钢股票数
    bank_stock_amount =  IntegerField()  # 沪深A股+创业板发出买入或追涨信号的银行股票数
    strong_pursuit_stock_amount =  IntegerField()  # 沪深A股+创业板发出强烈追涨信号的股票数
    strong_pursuit_stock_ratio =  FloatField() # 发出强烈追涨信号的股票比例
    pursuit_kdj_die_stock_amount =  IntegerField()  # 沪深A股+创业板发出追涨信号但KDJ死叉的股票数
    pursuit_kdj_die_stock_ratio = FloatField() # 发出追涨信号但KDJ死叉的股票占总的追涨股票的比例
    run_stock_amount =  IntegerField()  # 沪深A股+创业板发出逃顶信号的股票数
    run_stock_ratio = FloatField() # 发出逃顶信号的股票比例
    big_fall_after_multi_bank_iron = BooleanField() # 当有多只普钢或银行股发出追涨信号后，是否大跌：False 否，True 是
    four_days_pursuit_ratio_decrease = BooleanField() # 近四日追涨比例突然变小：False 否，True 是
    too_big_increase = BooleanField() # True：追涨比例大于3%   False：others
    futures = StringField(ddl='varchar(50)') # 期指交割日，格式：2016-11-18,2016-12-16 （以英文逗号分隔）
    method_1 = StringField(ddl='varchar(50)') # 方式1选出的股票名称，不能是3天内刚复牌的股票
    method_2 = StringField(ddl='varchar(50)') # 方式2选出的股票名称，不能是3天内刚复牌的股票
    recommendation = StringField(ddl='varchar(50)') # 操作建议
    created_at = FloatField(default=time.time)

