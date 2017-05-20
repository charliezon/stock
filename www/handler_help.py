#!/usr/bin/env python3
# -*- coding: utf-8 -*-

__author__ = 'Chaoliang Zhong'

import asyncio
from models import DailyParam, AccountRecord, Account, round_float, last_month
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

@asyncio.coroutine
async def get_profit(account_id, date):
    records = await AccountRecord.findAll('account_id=? and date=?', [account_id, date])
    if (len(records) == 0):
        return False
    return records[0].total_profit