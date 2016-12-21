#!/usr/bin/env python3
# -*- coding: utf-8 -*-

__author__ = 'Chaoliang Zhong'

import asyncio
from models import DailyParam

@asyncio.coroutine
async def get_stock_method(stock_name, buy_date):
    dps = await DailyParam.findAll('date<?', [buy_date], orderBy='date desc', limit=1)
    if len(dps) == 1:
        dp = dps[0]
        if dp.method_1 and dp.method_1 == stock_name:
            #return '<span class="uk-badge">方式一</span>'
            return 1
        elif dp.method_2 and dp.method_2 == stock_name:
            #return '<span class="uk-badge uk-badge-success">方式二</span>'
            return 2
    return False