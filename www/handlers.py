#!/usr/bin/env python3

# -*- coding: utf-8 -*-

__author__ = 'Chaoliang Zhong'

' url handlers '

import re, time, json, logging, hashlib, base64, asyncio

from coroweb import get, post

from models import User, next_id

@get('/')
def index(request):
    user = User(id='1', name='Charlie', admin=True, email='b@example.com', passwd='1234567890', image='about:blank')
    return {
        '__template__': 'account.html',
        'user': user
    }

@asyncio.coroutine
@get('/api/users')
async def api_get_users():
    users = await User.findAll(orderBy='created_at desc')
    for u in users:
        u.passwd = '******'
    return dict(users=users)