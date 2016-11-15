#!/usr/bin/env python3

# -*- coding: utf-8 -*-

__author__ = 'Chaoliang Zhong'


from urllib import request
from urllib.parse import quote
from urllib import error
from config import configs
import re
from models import today

def get_new_code(code):
    if code[:1] == '0' or code[:1] == '3':
        new_code = 'sz' + code;
    else:
        new_code = 'sh' + code;
    return new_code

def find_open_price(stock_code, year, month, day):
    if (year >= 2000):
        new_year = year - 2000
    else:
        new_year = year -1900
    new_code = get_new_code(stock_code)
    if len(str(month)) < 2:
        new_month = '0'+str(month)
    else:
        new_month = month
    if len(str(day)) < 2:
        new_day = '0'+str(day)
    else:
        new_day = day
    date = str(new_year)+str(new_month)+str(new_day)
    with request.urlopen('http://data.gtimg.cn/flashdata/hushen/daily/'+str(new_year)+'/'+new_code+'.js') as f:
        if f.status == 200:
            data = f.read().decode('utf-8')
            lines = data.split('\\n\\')
            pre_number = False
            for line in lines:
                numbers = line.split(' ')
                if (len(numbers) == 6):
                    if numbers[0].strip() == date:
                        return numbers[1]
                    elif numbers[0].strip() > date and pre_number:
                        return pre_number
                    elif numbers[0].strip() > date and not pre_number:
                        return find_open_price(stock_code, year-1, 12, 31)
                    if len(numbers) >= 2:
                        pre_number = numbers[1]

def find_close_price(stock_code, year, month, day):
    if (year >= 2000):
        new_year = year - 2000
    else:
        new_year = year -1900
    new_code = get_new_code(stock_code)
    if len(str(month)) < 2:
        new_month = '0'+str(month)
    else:
        new_month = month
    if len(str(day)) < 2:
        new_day = '0'+str(day)
    else:
        new_day = day
    date = str(new_year)+str(new_month)+str(new_day)
    with request.urlopen('http://data.gtimg.cn/flashdata/hushen/daily/'+str(new_year)+'/'+new_code+'.js') as f:
        if f.status == 200:
            data = f.read().decode('utf-8')
            lines = data.split('\\n\\')
            pre_number = False
            for line in lines:
                numbers = line.split(' ')
                if (len(numbers) == 6):
                    if numbers[0].strip() == date:
                        return numbers[2]
                    elif numbers[0].strip() > date and pre_number:
                        return pre_number
                    elif numbers[0].strip() > date and not pre_number:
                        return find_close_price(stock_code, year-1, 12, 31)
                    if len(numbers) >= 2:
                        pre_number = numbers[2]           

# http://suggest3.sinajs.cn/suggest/type=11,12,13,14,15&key=ptp
# http://suggest3.sinajs.cn/suggest/type=11,12,13,14,15&key=浦发银行
def get_stock_via_name(name):
    stocks = []
    with request.urlopen('http://suggest3.sinajs.cn/suggest/type=11,12,13,14,15&key='+quote(name)) as f:
        if f.status == 200:
            data = f.read()
            content = data.decode('gbk')
            content_list = content.split(r'"')
            if len(content_list) == 3:
                stock_list = content_list[1].split(r';')
                for stock in stock_list:
                    stock_info = stock.split(r',')
                    if len(stock_info) == 6:
                        stocks.append({'stock_code':stock_info[2], 'stock_name':stock_info[4]})
            return stocks

# http://qt.gtimg.cn/q=sz300001  创业板
# http://qt.gtimg.cn/q=sh600919 沪指
# http://qt.gtimg.cn/q=sz000858 深指
def get_stock_via_code(code):
    new_code = get_new_code(code)
    with request.urlopen('http://qt.gtimg.cn/q='+new_code) as f:
        if f.status == 200:
            data = f.read()
            content = data.decode('gbk')
            if content == 'pv_none_match=1;':
                return False
            else:
                content_list = content.split('~')
                if len(content_list) >= 2:
            	    return [{'stock_code':code, 'stock_name':content_list[1].replace(' ', '')}]
                else:
            	    return False
        else:
        	return False

def get_stock(code):
    if code[:1] == '0' or code[:1] == '3' or code[:1] == '6':
        return get_stock_via_code(code)
    else:
        return get_stock_via_name(code)

# TODO 如果date早于今天，则获取代码为stock_code的股票在date日期的收盘价，否则获取当前价格
# TODO 如果date早于今天，从cache中获取
# TODO 改成每天定时更新当天所有accout_records的stock_hold_records的current price
# TODO 如果时间晚于 15点，且股价不再变化，存入cache
def get_current_price(stock_code, date):
    numbers = date.split('-')
    return find_close_price(stock_code, int(numbers[0]), int(numbers[1]), int(numbers[2]))

def get_open_price(stock_code, date):
    numbers = date.split('-')
    return find_open_price(stock_code, int(numbers[0]), int(numbers[1]), int(numbers[2]))

def get_sell_price(stock_code, date):
    return round(get_open_price(stock_code, date)*1.04, 2)

# 印花税计算
def compute_stock_tax(buy, stock_price, stock_amount):
    if buy:
        return 0
    else:
        return stock_price*stock_amount*configs.tax_rate

# 过户费计算
def compute_exchange_fee(stock_code, stock_amount):
    if not (stock_code[:1] == '0' or stock_code[:1] == '3'):
        return stock_amount * configs.stock.exchange_fee_rate;
    else:
        return 0

# 佣金计算
def compute_security_fee(stock_price, stock_amount, commission_rate):
    security_fee = stock_amount * stock_price * commission_rate
    if security_fee < 5:
        security_fee = 5
    return security_fee


def compute_fee(buy, commission_rate, stock_code, stock_price, stock_amount):
    return compute_stock_tax(buy, stock_price, stock_amount) + compute_exchange_fee(stock_code, stock_amount) + compute_security_fee(stock_price, stock_amount, commission_rate)


# print(get_stock('300001'))
# print(get_stock('600919'))
# print(get_stock('000858'))
# print(get_stock('pfyh'))
# print(get_stock('ptp'))
# print(get_stock('trd'))
# print(get_stock('jsyh'))
# print(get_stock('wly'))
# print(get_stock('浦发银行'))
# print(get_stock('特锐德'))
# print(get_stock('五粮液'))
# print(get_stock('建设银行'))

print(find_open_price('600000', 2011, 1, 3))
print(find_open_price('600000', 2011, 1, 14))
print(find_open_price('600000', 2011, 2, 15))
print(find_open_price('600000', 2011, 3, 20))
print(find_open_price('600000', 2011, 3, 19))
print(get_open_price('600000', '2011-01-03'))
print(get_open_price('600000', '2011-01-14'))
print(get_open_price('600000', '2011-02-15'))
print(get_open_price('600000', '2011-03-20'))
print(get_open_price('600000', '2011-03-19'))


