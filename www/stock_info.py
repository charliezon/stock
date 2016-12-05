#!/usr/bin/env python3

# -*- coding: utf-8 -*-

__author__ = 'Chaoliang Zhong'

import re, logging
from urllib import request, error
from urllib.parse import quote
from config import configs
from models import today, round_float

def current_shanghai_index_info():
    result = False
    try:
        with request.urlopen('http://hq.sinajs.cn/list=s_sh000001') as f:
            if f.status == 200:
                data = f.read().decode('gb2312')
                numbers = data.split(',');
                if (len(numbers) == 6):
                    try:
                        result = float(numbers[1].strip())
                    except ValueError as e:
                        logging.error(e)
    except error.HTTPError as e:
        logging.error(e)
    except error.URLError as e:
        logging.error(e)
    finally:
        return result

def get_shanghai_index_info(date):
    index = False
    if date >= today():
        index = current_shanghai_index_info()
    else:
        numbers = date.split('-')
        index = find_close_price('000001', int(numbers[0]), int(numbers[1]), int(numbers[2]))
    return index

def get_new_code(code):
    if (code[:1] == '0' or code[:1] == '3') and (code != '000001'):
        return 'sz' + code;
    else:
        return 'sh' + code;

def find_price(stock_code, pos):
    result = False
    new_code = get_new_code(stock_code)
    try:
        with request.urlopen('http://hq.sinajs.cn/list='+new_code) as f:
            if f.status == 200:
                data = f.read().decode('gb2312')
                numbers = data.split(',');
                if (len(numbers) >= pos+1):
                    try:
                        result = float(numbers[pos].strip())
                    except ValueError as e:
                        logging.error(e)
    except error.HTTPError as e:
        logging.error(e)
    except error.URLError as e:
        logging.error(e)
    finally:
        return result


def find_current_price(stock_code):
    return find_price(stock_code, 3)

def find_open_price_with_code(stock_code):
    return find_price(stock_code, 1)

def find_open_price(stock_code, year, month, day):
    result = False
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
    try:
        with request.urlopen('http://data.gtimg.cn/flashdata/hushen/daily/'+str(new_year)+'/'+new_code+'.js') as f:
            if f.status == 200:
                data = f.read().decode('utf-8')
                lines = data.split('\\n\\')
                pre_number = False
                for line in lines:
                    numbers = line.split(' ')
                    if (len(numbers) == 6):
                        if numbers[0].strip() == date:
                            try:
                                result = float(numbers[1].strip())
                                break
                            except ValueError as e:
                                logging.error(e)
                        elif numbers[0].strip() > date and pre_number:
                            try:
                                result = float(pre_number.strip())
                                break
                            except ValueError as e:
                                logging.error(e)
                        elif numbers[0].strip() > date and not pre_number:
                            result = find_open_price(stock_code, year-1, 12, 31)
                            break
                        if len(numbers) >= 2:
                            pre_number = numbers[1]
    except error.HTTPError as e:
        logging.error(e)
    except error.URLError as e:
        logging.error(e)
    finally:
        return result

def find_close_price(stock_code, year, month, day):
    result = False
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
    try:
        with request.urlopen('http://data.gtimg.cn/flashdata/hushen/daily/'+str(new_year)+'/'+new_code+'.js') as f:
            if f.status == 200:
                data = f.read().decode('utf-8')
                lines = data.split('\\n\\')
                pre_number = False
                last_day = False
                for line in lines:
                    numbers = line.split(' ')
                    if (len(numbers) == 6):
                        last_day = numbers[0].strip()
                        if last_day == date:
                            try:
                                result = float(numbers[2].strip())
                                break
                            except ValueError as e:
                                logging.error(e)
                        elif last_day > date and pre_number:
                            try:
                                result = float(pre_number.strip())
                                break
                            except ValueError as e:
                                logging.error(e)
                        elif last_day > date and not pre_number:
                            result = find_close_price(stock_code, year-1, 12, 31)
                            break
                        if len(numbers) >= 2:
                            pre_number = numbers[2]
                if last_day and date > last_day and pre_number:
                    result = pre_number
    except error.HTTPError as e:
        logging.error(e)
    except error.URLError as e:
        logging.error(e)
    finally:
        return result

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

def get_current_price(stock_code, date):
    current_price = False
    if date == today():
        current_price = find_current_price(stock_code)
    if not current_price:
        numbers = date.split('-')
        current_price = find_close_price(stock_code, int(numbers[0]), int(numbers[1]), int(numbers[2]))
    if current_price:
        return current_price
    else:
        return 0

def get_open_price(stock_code, date):
    if date != today():
        numbers = date.split('-')
        return find_open_price(stock_code, int(numbers[0]), int(numbers[1]), int(numbers[2]))
    else:
        return find_open_price_with_code(stock_code)

def get_sell_price(stock_code, date):
    open_price = get_open_price(stock_code, date)
    if open_price:
        return round_float(open_price*1.04)
    else:
        return 0

# 印花税计算
def compute_stock_tax(buy, stock_price, stock_amount):
    if buy:
        return 0
    else:
        return stock_price*stock_amount*configs.stock.tax_rate

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
    fee = compute_stock_tax(buy, stock_price, stock_amount) + compute_exchange_fee(stock_code, stock_amount) + compute_security_fee(stock_price, stock_amount, commission_rate)
    return round_float(fee)


print('2017-11-27', get_shanghai_index_info('2017-11-27'))
print('2016-11-27', get_shanghai_index_info('2016-11-27'))
print('2016-11-26', get_shanghai_index_info('2016-11-26'))
print('2016-11-25', get_shanghai_index_info('2016-11-25'))
print('2016-11-24', get_shanghai_index_info('2016-11-24'))
print('2016-11-23', get_shanghai_index_info('2016-11-23'))
print('2016-11-22', get_shanghai_index_info('2016-11-22'))
print('2016-11-21', get_shanghai_index_info('2016-11-21'))
print('2016-11-20', get_shanghai_index_info('2016-11-20'))
print('2016-11-19', get_shanghai_index_info('2016-11-19'))
print('2016-11-18', get_shanghai_index_info('2016-11-18'))


