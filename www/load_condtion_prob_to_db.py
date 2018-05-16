#!/usr/bin/env python3
# -*- coding: utf-8 -*-

__author__ = 'Chaoliang Zhong'

import os
import json

from decimal import Decimal as D
import math
import pymysql
pymysql.install_as_MySQLdb()
import MySQLdb
from config import configs

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

def load_cache(path):
  cache = {}
  if not os.path.exists(path):
    return cache
  with open(path, 'r') as f:
    cache = json.load(f)
  return cache

conn= MySQLdb.connect(
        host=configs.db.host,
        port = 3306,
        user='root',
        passwd='rootroot',
        db ='stock',
        charset="utf8"
        )
cur = conn.cursor()

cache = load_cache('data/cache_1.034_0.905.json')

id = 1

for key in cache:
    keys = key.split(' and ')

    if (len(keys) == 12):
        if (keys[0] == 'E1'):
            e1 = 1
        else:
            e1 = 0

        if (keys[1] == 'E2'):
            e2 = 1
        else:
            e2 = 0

        if (keys[2] == 'E3'):
            e3 = 1
        else:
            e3 = 0

        if (keys[3] == 'E4'):
            e4 = 1
        else:
            e4 = 0

        profit_sign = keys[4]
        turnover_sign = keys[5]
        increase_sign = keys[6]

        if (keys[7] == 'buy'):
            buy_or_follow = 1
        elif (keys[7] == 'follow'):
            buy_or_follow = 2
        elif (keys[7] == 'all'):
            buy_or_follow = 3

        win_percent = round_float(float(keys[8]), 3)
        lose_percent = round_float(float(keys[9]), 3)
        lose_cache = round_float(float(keys[10]), 3)
        days = int(keys[11])
        all_numerator = int(cache[key]['numerator'])
        all_denominator = int(cache[key]['denominator'])
        all_result = cache[key]['result']

        profit_key = ' and '.join([keys[0], keys[1], keys[2], keys[3], keys[4], keys[7], keys[8], keys[9], keys[10], keys[11]])
        profit_record = cache[profit_key]
        if profit_record is not None:
            profit_numerator = int(profit_record['numerator'])
            profit_denominator = int(profit_record['denominator'])
            profit_result = profit_record['result']

        turnover_key = ' and '.join([keys[0], keys[1], keys[2], keys[3], keys[5], keys[7], keys[8], keys[9], keys[10], keys[11]])
        turnover_record = cache[turnover_key]
        if turnover_record is not None:
            turnover_numerator = int(turnover_record['numerator'])
            turnover_denominator = int(turnover_record['denominator'])
            turnover_result = turnover_record['result']

        increase_key = ' and '.join([keys[0], keys[1], keys[2], keys[3], keys[6], keys[7], keys[8], keys[9], keys[10], keys[11]])
        increase_record = cache[increase_key]
        if increase_record is not None:
            increase_numerator = int(increase_record['numerator'])
            increase_denominator = int(increase_record['denominator'])
            increase_result = increase_record['result']

        sqli="insert into condition_prob values(%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)"
        cur.execute(sqli , (str(id), e1, e2, e3, e4, profit_sign, turnover_sign, increase_sign, buy_or_follow, win_percent, lose_percent, lose_cache, days, all_numerator, all_denominator, all_result, profit_numerator, profit_denominator, profit_result, turnover_numerator, turnover_denominator, turnover_result, increase_numerator, increase_denominator, increase_result))
        id += 1

stock_detail = load_cache('data/list_1.034_0.905.json')

id = 0
for stock in stock_detail:
    if (stock['signal'] == 'buy'):
        buy_or_follow = 1
    elif (stock['signal'] == 'follow'):
        buy_or_follow = 2
    elif (stock['signal'] == 'all'):
        buy_or_follow = 3

    if (stock['e1'] == 'E1'):
        e1 = 1
    else:
        e1 = 0

    if (stock['e2'] == 'E2'):
        e2 = 1
    else:
        e2 = 0

    if (stock['e3'] == 'E3'):
        e3 = 1
    else:
        e3 = 0

    if (stock['e4'] == 'E4'):
        e4 = 1
    else:
        e4 = 0

    if stock['result'] == 'success':
        result = 1
    else:
        result = 0
    sqli="insert into stock_success_detail values(%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)"
    cur.execute(sqli , (str(id), stock['date'], stock['name'], buy_or_follow, e1, e2, e3, e4, stock['winner'], stock['turnover'], stock['increase'], result))
    id += 1

cur.close()
conn.commit()
conn.close()





