#!/usr/bin/env python3
# -*- coding: utf-8 -*-

__author__ = 'Chaoliang Zhong'

import asyncio
from models import DailyParam, AccountRecord, Account, round_float, last_month
from stock_info import get_index_info
import logging

@asyncio.coroutine
async def get_stock_method(stock_name, buy_date):
    dps = await DailyParam.findAll('date<?', [buy_date], orderBy='date desc', limit=1)
    if len(dps) == 1:
        dp = dps[0]
        if dp.method_1 and dp.method_1 == stock_name:
            return 1
        elif dp.method_2 and dp.method_2 == stock_name:
            return 2
    return False

@asyncio.coroutine
async def get_average_cost(account_id, start_date, end_date):
    records = await AccountRecord.findAll('account_id=? and date>=? and date<=?', [account_id, start_date, end_date], orderBy='date desc')
    if len(records) <= 1:
        return False
    cost = records[len(records) - 1].total_assets
    origin_cost = cost
    origin_principle = records[len(records) - 1].principle
    for i in range(1, len(records) - 1):
        cost += (records[i].principle - origin_principle + origin_cost)
    return float(cost) / float(len(records) - 1)


@asyncio.coroutine
async def get_profit_rate_by_month(account_id, year, month):
    last_mon = last_month('-'.join([year, month]))
    records = await AccountRecord.findAll('account_id=? and date>=? and date<=?', [account_id, last_mon+'-01', last_mon+'-31'], orderBy='date desc')
    if len(records) > 0:
        start_date = records[0].date
    else:
        start_date = '-'.join([year, month, '01'])
    return await get_profit_rate(account_id, start_date, '-'.join([year, month, '31']))

@asyncio.coroutine
async def get_profit_rate(account_id, start_date, end_date):
    account = await Account.find(account_id)
    if not account:
        return False
    records = await AccountRecord.findAll('account_id=? and date>=? and date<=?', [account_id, start_date, end_date], orderBy='date desc')
    if len(records) == 0:
        return False
    end_date = records[0].date
    start_date = records[len(records) - 1].date
    average_cost = await get_average_cost(account_id, start_date, end_date)
    if not average_cost:
        return False
    end_date_profit = await get_profit(account_id, end_date)
    start_date_profit = await get_profit(account_id, start_date)
    return {
        'account_name': account.name,
        'cost': round_float(average_cost),
        'profit': round_float(end_date_profit - start_date_profit),
        'profit_rate': round_float((end_date_profit - start_date_profit) * 100 / average_cost)
    }

def get_shenzhen_profit_rate_by_month(year, month):
    return get_index_profit_rate_by_month('399001', '深证成指', year, month)

def get_shanghai_profit_rate_by_month(year, month):
    return get_index_profit_rate_by_month('000001', '上证综指', year, month)

def get_shenzhen_profit_rate(start_date, end_date):
    return get_index_profit_rate('399001', '深证成指', start_date, end_date)

def get_shanghai_profit_rate(start_date, end_date):
    return get_index_profit_rate('000001', '上证综指', start_date, end_date)

def get_index_profit_rate_by_month(index, index_name, year, month):
    last_mon = last_month('-'.join([year, month]))
    start_date = last_mon+'-31'
    end_date = '-'.join([year, month, '31'])
    return get_index_profit_rate(index, index_name, start_date, end_date)

def get_index_profit_rate(index, index_name, start_date, end_date):
    start_value = get_index_info(index, start_date)
    end_value = get_index_info(index, end_date)
    if (start_value and end_value):
        return {
            'account_name': index_name,
            'cost': round_float(start_value),
            'profit': round_float(end_value - start_value),
            'profit_rate': round_float((end_value - start_value) * 100 / start_value)
        }
    else:
        return False

@asyncio.coroutine
async def get_profit(account_id, date):
    records = await AccountRecord.findAll('account_id=? and date=?', [account_id, date])
    if (len(records) == 0):
        return False
    return records[0].total_profit