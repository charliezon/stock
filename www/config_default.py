#!/usr/bin/env python3

# -*- coding: utf-8 -*-



'''

Default configurations.

'''



__author__ = 'Chaoliang Zhong'



configs = {

    'debug': True,

    'db': {

        'host': '127.0.0.1',

        'port': 3306,

        'user': 'root',

        'password': 'rootroot',

        'db': 'stock'

    },

    'session': {

        'secret': 'stock'

    },

    'stock': {
        'exchange_fee_rate': 0.0006,
        'tax_rate': 0.001,
        'account_record_items_on_page': 20,
        'stock_trade_items_on_page': 20,
        'param_items_on_page': 20,
        'refresh_interval': 0.5,
        'max_stock_hold_days': 15
    },

}