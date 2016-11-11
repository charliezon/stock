#!/usr/bin/env python3
# -*- coding: utf-8 -*-

__author__ = 'Chaoliang Zhong'

' url handlers '

import re, time, json, logging, hashlib, base64, asyncio

from aiohttp import web
from coroweb import get, post
from apis import APIValueError, APIResourceNotFoundError, APIError, APIPermissionError

from models import User, Account, next_id
from config import configs

COOKIE_NAME = 'stocksession'
_COOKIE_KEY = configs.session.secret


def user2cookie(user, max_age):
    '''
    Generate cookie str by user.
    '''
    # build cookie string by: id-expires-sha1
    expires = str(int(time.time() + max_age))
    s = '%s-%s-%s-%s' % (user.id, user.passwd, expires, _COOKIE_KEY)
    L = [user.id, expires, hashlib.sha1(s.encode('utf-8')).hexdigest()]
    return '-'.join(L)

@asyncio.coroutine
async def cookie2user(cookie_str):
    '''
    Parse cookie and load user if cookie is valid.
    '''
    if not cookie_str:
        return None
    try:
        L = cookie_str.split('-')
        if len(L) != 3:
            return None
        uid, expires, sha1 = L
        if int(expires) < time.time():
            return None
        user = await User.find(uid)
        if user is None:
            return None
        s = '%s-%s-%s-%s' % (uid, user.passwd, expires, _COOKIE_KEY)
        if sha1 != hashlib.sha1(s.encode('utf-8')).hexdigest():
            logging.info('invalid sha1')
            return None
        user.passwd = '******'
        return user
    except Exception as e:
        logging.exception(e)
        return None

@get('/')
def index(request):
    if not has_logged_in(request):
        return web.HTTPFound('/signin')
    return web.HTTPFound('/account')

@get('/register')
def register():
    return {
        '__template__': 'register.html'
    }

@get('/signin')
def signin():
    return {
        '__template__': 'signin.html'
    }

@asyncio.coroutine
@post('/api/authenticate')
async def authenticate(*, name, passwd):
    if not name:
        raise APIValueError('name', 'Invalid name.')
    if not passwd:
        raise APIValueError('passwd', 'Invalid password.')
    users = await User.findAll('name=?', [name])
    if len(users) == 0:
        raise APIValueError('name', 'Name not exist.')
    user = users[0]
    # check passwd:
    sha1 = hashlib.sha1()
    sha1.update(user.id.encode('utf-8'))
    sha1.update(b':')
    sha1.update(passwd.encode('utf-8'))
    if user.passwd != sha1.hexdigest():
        raise APIValueError('passwd', 'Invalid password.')
    # authenticate ok, set cookie:
    r = web.Response()
    r.set_cookie(COOKIE_NAME, user2cookie(user, 86400), max_age=86400, httponly=True)
    user.passwd = '******'
    r.content_type = 'application/json'
    r.body = json.dumps(user, ensure_ascii=False).encode('utf-8')
    return r

@get('/signout')
def signout(request):
    referer = request.headers.get('Referer')
    r = web.HTTPFound(referer or '/')
    r.set_cookie(COOKIE_NAME, '-deleted-', max_age=0, httponly=True)
    logging.info('user signed out.')
    return r

@get('/account/create')
def create_account(request):
    if not has_logged_in(request):
        return web.HTTPFound('/signin')
    return {
        '__template__': 'create_account.html',
        'action': '/api/accounts'
    }

_RE_EMAIL = re.compile(r'^[a-z0-9\.\-\_]+\@[a-z0-9\-\_]+(\.[a-z0-9\-\_]+){1,4}$')
_RE_SHA1 = re.compile(r'^[0-9a-f]{40}$')

@asyncio.coroutine
@post('/api/users')
async def api_register_user(*, email, name, passwd):
    if not name or not name.strip():
        raise APIValueError('name')
    if not email or not _RE_EMAIL.match(email):
        raise APIValueError('email')
    if not passwd or not _RE_SHA1.match(passwd):
        raise APIValueError('passwd')
    users = await User.findAll('email=?', [email])
    if len(users) > 0:
        raise APIError('register:failed', 'email', 'Email is already in use.')
    users = await User.findAll('name=?', [name])
    if len(users) > 0:
        raise APIError('register:failed', 'name', 'Name is already in use.')
    uid = next_id()
    sha1_passwd = '%s:%s' % (uid, passwd)
    user = User(id=uid, name=name.strip(), email=email, passwd=hashlib.sha1(sha1_passwd.encode('utf-8')).hexdigest(), image='http://www.gravatar.com/avatar/%s?d=mm&s=120' % hashlib.md5(email.encode('utf-8')).hexdigest())
    await user.save()
    # make session cookie:
    r = web.Response()
    r.set_cookie(COOKIE_NAME, user2cookie(user, 86400), max_age=86400, httponly=True)
    user.passwd = '******'
    r.content_type = 'application/json'
    r.body = json.dumps(user, ensure_ascii=False).encode('utf-8')
    return r

def check_admin(request):
    if request.__user__ is None or not request.__user__.admin:
        raise APIPermissionError()

def has_logged_in(request):
    return not request.__user__ is None

def must_log_in(request):
    if not has_logged_in(request):
        raise APIPermissionError()
    else:
        pass

@asyncio.coroutine
@get('/account')
async def get_default_account(request):
    if not has_logged_in(request):
        return web.HTTPFound('/signin')
    all_accounts = await Account.findAll('user_id=?', [request.__user__.id])
    if (len(all_accounts) > 0):
        account = all_accounts[0]
    else:
        return web.HTTPFound('/account/create')
    return {
        '__template__': 'account.html',
        'account': account,
        'accounts': all_accounts
    }

@asyncio.coroutine
@get('/account/{id}')
async def get_account(request, *, id):
    if not has_logged_in(request):
        return web.HTTPFound('/signin')
    accounts = await Account.findAll('id=? and user_id=?', [id, request.__user__.id])
    all_accounts = await Account.findAll('user_id=?', [request.__user__.id])
    if (len(accounts) > 0):
        account = accounts[0]
    elif (len(all_accounts) > 0):
        account = all_accounts[0]
    else:
        raise APIPermissionError()
    return {
        '__template__': 'account.html',
        'account': account,
        'accounts': all_accounts
    }

@asyncio.coroutine
@get('/api/accounts/{id}')
async def api_get_account(request, *, id):
    must_log_in(request)
    account = await Account.find(id)
    return account

@asyncio.coroutine
@post('/api/accounts')
async def api_create_account(request, *, name, commission_rate, initial_funding):
    must_log_in(request)
    if not name or not name.strip():
        raise APIValueError('name', '账户名称不能为空')
    accounts = await Account.findAll('name=? and user_id=?', [name.strip(), request.__user__.id])
    if len(accounts) > 0:
        raise APIValueError('name', '账户名称已被用')
    try:
        commission_rate = float(commission_rate)
    except ValueError as e:
        raise APIValueError('commission_rate', '手续费率填写不正确')
    try:
        initial_funding = float(initial_funding)
    except ValueError as e:
        raise APIValueError('initial_funding', '初始资金填写不正确')
    account = Account(user_id=request.__user__.id, name=name.strip(), commission_rate=commission_rate, initial_funding=initial_funding)
    await account.save()
    return account