#!/usr/bin/env python3

# -*- coding: utf-8 -*-

__author__ = 'Chaoliang Zhong'


from urllib import request
from urllib.parse import quote

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
    if code[:1] == '0' or code[:1] == '3':
        new_code = 'sz' + code;
    else:
        new_code = 'sh' + code;
    with request.urlopen('http://qt.gtimg.cn/q='+new_code) as f:
        if f.status == 200:
            data = f.read()
            content = data.decode('gbk')
            if content == 'pv_none_match=1;':
                return False
            else:
                content_list = content.split('~')
                if len(content_list) >= 2:
            	    return [{'stock_code':code, 'stock_name':content_list[1]}]
                else:
            	    return False
        else:
        	return False

def get_stock(code):
    if code[:1] == '0' or code[:1] == '3' or code[:1] == '6':
        return get_stock_via_code(code)
    else:
        return get_stock_via_name(code)


print(get_stock('300001'))
print(get_stock('600919'))
print(get_stock('000858'))
print(get_stock('pfyh'))
print(get_stock('ptp'))
print(get_stock('trd'))
print(get_stock('jsyh'))
print(get_stock('wly'))
print(get_stock('浦发银行'))
print(get_stock('特锐德'))
print(get_stock('五粮液'))
print(get_stock('建设银行'))