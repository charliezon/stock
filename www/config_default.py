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
        'guohu_rate': 0.0006
    },

}