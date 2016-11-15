#!/usr/bin/env python3
# -*- coding: utf-8 -*-

__author__ = 'Chaoliang Zhong'

' url handlers '

import re, time, json, logging, hashlib, base64, asyncio

from aiohttp import web
from coroweb import get, post
from apis import APIValueError, APIResourceNotFoundError, APIError, APIPermissionError

from models import User, Account, AccountRecord, StockHoldRecord, AccountAssetChange, next_id, today
from config import configs
from stock_info import get_current_price

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
        return {
            '__template__': 'index.html'
        }
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
    r = web.HTTPFound('/')
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

@get('/account/advanced/create')
def advanced_create_account(request):
    if not has_logged_in(request):
        return web.HTTPFound('/signin')
    return {
        '__template__': 'advanced_create_account.html',
        'action': '/api/advanced/accounts'
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
async def find_account_record(account_id, date):
    all_account_records = await AccountRecord.findAll('account_id=? and date=?', [account_id, date])
    if len(all_account_records) <=0:
        pre_account_records = await AccountRecord.findAll('account_id=? and date<?', [account_id, date], orderBy='date desc', limit=1)
        if len(pre_account_records) <=0:
            raise APIPermissionError()
        try:
            account_record = AccountRecord(
                date=date, 
                account_id=account_id, 
                stock_position=pre_account_records[0].stock_position,
                security_funding=pre_account_records[0].security_funding, 
                bank_funding=pre_account_records[0].bank_funding, 
                total_stock_value=pre_account_records[0].total_stock_value,
                total_assets=pre_account_records[0].total_assets,
                float_profit_lost=pre_account_records[0].float_profit_lost,
                total_profit=pre_account_records[0].total_profit,
                principle=pre_account_records[0].principle)
            await account_record.save()

            stocks = await StockHoldRecord.findAll('account_record_id=?', [pre_account_records[0].id])
            if len(stocks) > 0:
                total_stock_value = 0
                for stock in stocks:
                    new_stock = StockHoldRecord(
                        account_record_id=account_record.id,
                        stock_code=stock.stock_code,
                        stock_name=stock.stock_name,
                        stock_amount=stock.stock_amount,
                        stock_current_price=stock.stock_current_price,
                        stock_buy_price=stock.stock_buy_price,
                        stock_sell_price=stock.stock_sell_price,
                        stock_buy_date=stock.stock_buy_date)
                    current_price = get_current_price(stock.stock_code, date)
                    if current_price:
                        new_stock.stock_current_price = current_price
                    total_stock_value = total_stock_value + new_stock.stock_amount * new_stock.stock_current_price
                    await new_stock.save()
                account_record.total_stock_value = total_stock_value
                account_record.total_assets = account_record.security_funding + account_record.bank_funding + account_record.total_stock_value
                account_record.total_profit = account_record.total_assets - account_record.principle
                account_record.stock_position = account_record.total_stock_value / account_record.total_assets
                account_record.float_profit_lost = account_record.float_profit_lost   # TODO 根据股票当前价更新
        except Error as e:
            raise APIPermissionError()
    else:
        account_record = all_account_records[0]
    return account_record

@asyncio.coroutine
@get('/account')
async def get_default_account(request):
    if not has_logged_in(request):
        return web.HTTPFound('/signin')
    all_accounts = await Account.findAll('user_id=?', [request.__user__.id])
    if (len(all_accounts) > 0):
        account = all_accounts[0]
        return web.HTTPFound('/account/'+account.id)
    else:
        return web.HTTPFound('/account/create')

@asyncio.coroutine
@get('/account/')
async def get_account_index(request):
    return web.HTTPFound('/account')

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
    all_account_records = await AccountRecord.findAll('account_id=?', [id], orderBy='date desc')
    for account_record in all_account_records:
        stock_hold_records = await StockHoldRecord.findAll('account_record_id=?', [account_record.id], orderBy='stock_buy_date')
        if len(stock_hold_records)<10:
            for x in range(10-len(stock_hold_records)):
                stock_hold_records.append({'stock_name':'-', 'stock_amount':0, 'stock_current_price':0})
        account_record.stock_hold_records = stock_hold_records[:10]
    return {
        '__template__': 'account.html',
        'account': account,
        'accounts': all_accounts,
        'most_recent_account_record': all_account_records[0],
        'all_account_records': all_account_records,
        'buy_action': '/api/buy',
        'sell_action': '/api/sell',
        'add_bank_funding_action' : '/api/add_bank_funding',
        'minus_bank_funding_action' : '/api/minus_bank_funding',
        'add_security_funding_action' : '/api/add_security_funding',
        'minus_security_funding_action' : '/api/minus_security_funding'
    }

@asyncio.coroutine
@get('/api/accounts/{id}')
async def api_get_account(request, *, id):
    must_log_in(request)
    account = await Account.find(id)
    return account

@asyncio.coroutine
@post('/api/accounts')
async def api_create_account(request, *, name, commission_rate, initial_funding, date):
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
    if date is None:
        raise APIValueError('date', '日期不能为空')
    if date.strip() == '':
        raise APIValueError('date', '请选择日期')
    if date.strip() > today():
        raise APIValueError('date', '日期不能晚于今天')
    account = Account(user_id=request.__user__.id, name=name.strip(), commission_rate=commission_rate, initial_funding=initial_funding)
    await account.save()
    try:
        account_record = AccountRecord(date=date, account_id=account.id, stock_position=0, security_funding=0, bank_funding=initial_funding, total_stock_value=0, total_assets=initial_funding, float_profit_lost=0, total_profit=0, principle=initial_funding)
        await account_record.save()
    except Error as e:
        account.remove()
        raise APIValueError('name', '创建账户失败')
    return account

@asyncio.coroutine
@post('/api/advanced/accounts')
async def api_advanced_create_account(request, *, name, commission_rate, initial_funding, initial_bank_funding, initial_security_funding, date):
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
        raise APIValueError('initial_funding', '初始本金填写不正确')
    try:
        initial_bank_funding = float(initial_bank_funding)
    except ValueError as e:
        raise APIValueError('initial_bank_funding', '初始银行资金填写不正确')
    if initial_bank_funding<0:
        raise APIValueError('initial_bank_funding', '初始银行资金必须大于0')
    try:
        initial_security_funding = float(initial_security_funding)
    except ValueError as e:
        raise APIValueError('initial_security_funding', '初始银证资金填写不正确')
    if initial_security_funding<0:
        raise APIValueError('initial_security_funding', '初始银证资金必须大于0')
    if date is None:
        raise APIValueError('date', '日期不能为空')
    if date.strip() == '':
        raise APIValueError('date', '请选择日期')
    if date.strip() > today():
        raise APIValueError('date', '日期不能晚于今天')
    account = Account(user_id=request.__user__.id, name=name.strip(), commission_rate=commission_rate, initial_funding=initial_funding)
    await account.save()
    try:
        account_record = AccountRecord(date=date, account_id=account.id, stock_position=0, security_funding=initial_security_funding, bank_funding=initial_bank_funding, total_stock_value=0, total_assets=initial_security_funding+initial_bank_funding, float_profit_lost=0, total_profit=initial_security_funding+initial_bank_funding-initial_funding, principle=initial_funding)
        await account_record.save()
    except Error as e:
        account.remove()
        raise APIValueError('name', '创建账户失败')
    return account

@asyncio.coroutine
@post('/api/buy')
async def api_buy(request, *, stock_name, stock_code, stock_price, stock_amount, date, account_id):
    must_log_in(request)
    if not stock_name or not stock_name.strip():
        raise APIValueError('stock_name', '股票名称不能为空')
    if not stock_code or not stock_code.strip():
        raise APIValueError('stock_code', '股票代码不能为空')
    try:
        stock_price = float(stock_price)
    except ValueError as e:
        raise APIValueError('stock_price', '股票价格填写不正确')
    if stock_price<=0:
        raise APIValueError('stock_price', '股票价格必须大于0')
    try:
        stock_amount = int(stock_amount)
    except ValueError as e:
        raise APIValueError('stock_amount', '股票数量填写不正确')
    if stock_amount <=  0:
        raise APIValueError('stock_amount', '股票数量必须大于0')
    if stock_amount % 100 != 0:
        raise APIValueError('stock_amount', '股票数量必须为100的整数')
    if date is None:
        raise APIValueError('date', '日期不能为空')
    if date.strip() == '':
        raise APIValueError('date', '请选择日期')
    if date.strip() > today():
        raise APIValueError('date', '日期不能晚于今天')

    accounts = await Account.findAll('user_id=? and id=?', [request.__user__.id, account_id])
    if len(accounts) <=0:
        raise APIPermissionError()

    account_record = await find_account_record(account_id, date.strip())

    yinhuashui = 0
    guohufei = 0
    if not (stock_code[:1] == '0' or stock_code[:1] == '3'):
        guohufei = stock_amount * configs.stock.guohu_rate;
    yongjin = stock_amount * stock_price * accounts[0].commission_rate
    if yongjin < 5:
        yongjin = 5

    money = stock_amount * stock_price + yongjin + guohufei
    if money > account_record.security_funding:
        raise APIValueError('stock_name', '股票买入金额（'+str(money)+'）超过可用银证资金（'+str(account_record.security_funding)+'）')

    account_record.security_funding = account_record.security_funding - money
    current_price = get_current_price(stock_code.strip(), date.strip())
    account_record.total_stock_value = account_record.total_stock_value + stock_amount*current_price
    account_record.total_assets = account_record.total_stock_value + account_record.bank_funding + account_record.security_funding
    if account_record.total_assets >0:
        account_record.stock_position = account_record.total_stock_value / account_record.total_assets
    else:
        account_record.stock_position = 0
    account_record.total_profit = account_record.total_assets - account_record.principle
    # TODO 根据各只股票的当前价计算
    account_record.float_profit_lost = 0

    await account_record.update()

    # stock hold record增加一条记录
    
    return accounts[0]



@asyncio.coroutine
@post('/api/add_security_funding')
async def api_add_security_funding(request, *, funding_amount, date, account_id):
    must_log_in(request)
    try:
        funding_amount = float(funding_amount)
    except ValueError as e:
        raise APIValueError('funding_amount', '金额填写不正确')
    if funding_amount <=  0:
        raise APIValueError('funding_amount', '金额必须大于0')
    if date is None:
        raise APIValueError('date', '日期不能为空')
    if date.strip() == '':
        raise APIValueError('date', '请选择日期')
    if date.strip() > today():
        raise APIValueError('date', '日期不能晚于今天')

    accounts = await Account.findAll('user_id=? and id=?', [request.__user__.id, account_id])
    if len(accounts) <=0:
        raise APIPermissionError()

    account_record = await find_account_record(account_id, date.strip())

    if account_record.bank_funding < funding_amount:
        raise APIValueError('funding_amount', '转账金额不足')

    account_record.bank_funding = account_record.bank_funding - funding_amount
    account_record.security_funding = account_record.security_funding + funding_amount
    await account_record.update()

    security_funding_change = AccountAssetChange(
        account_id=account_id,
        change_amount=funding_amount,
        add_or_minus=True,
        security_or_bank=True,
        date=date)

    await security_funding_change.save()

    bank_funding_change = AccountAssetChange(
        account_id=account_id,
        change_amount=funding_amount,
        add_or_minus=False,
        security_or_bank=False,
        date=date)

    await bank_funding_change.save()

    return accounts[0]


@asyncio.coroutine
@post('/api/minus_security_funding')
async def api_minus_security_funding(request, *, funding_amount, date, account_id):
    must_log_in(request)
    try:
        funding_amount = float(funding_amount)
    except ValueError as e:
        raise APIValueError('funding_amount', '金额填写不正确')
    if funding_amount <=  0:
        raise APIValueError('funding_amount', '金额必须大于0')
    if date is None:
        raise APIValueError('date', '日期不能为空')
    if date.strip() == '':
        raise APIValueError('date', '请选择日期')
    if date.strip() > today():
        raise APIValueError('date', '日期不能晚于今天')

    accounts = await Account.findAll('user_id=? and id=?', [request.__user__.id, account_id])
    if len(accounts) <=0:
        raise APIPermissionError()

    account_record = await find_account_record(account_id, date.strip())

    if account_record.security_funding < funding_amount:
        raise APIValueError('funding_amount', '转账金额不足')

    account_record.bank_funding = account_record.bank_funding + funding_amount
    account_record.security_funding = account_record.security_funding - funding_amount
    await account_record.update()

    security_funding_change = AccountAssetChange(
        account_id=account_id,
        change_amount=funding_amount,
        add_or_minus=False,
        security_or_bank=True,
        date=date)

    await security_funding_change.save()

    bank_funding_change = AccountAssetChange(
        account_id=account_id,
        change_amount=funding_amount,
        add_or_minus=True,
        security_or_bank=False,
        date=date)

    await bank_funding_change.save()

    return accounts[0]

@asyncio.coroutine
@post('/api/add_bank_funding')
async def api_add_bank_funding(request, *, funding_amount, date, account_id):
    must_log_in(request)
    try:
        funding_amount = float(funding_amount)
    except ValueError as e:
        raise APIValueError('funding_amount', '金额填写不正确')
    if funding_amount <=  0:
        raise APIValueError('funding_amount', '金额必须大于0')
    if date is None:
        raise APIValueError('date', '日期不能为空')
    if date.strip() == '':
        raise APIValueError('date', '请选择日期')
    if date.strip() > today():
        raise APIValueError('date', '日期不能晚于今天')

    accounts = await Account.findAll('user_id=? and id=?', [request.__user__.id, account_id])
    if len(accounts) <=0:
        raise APIPermissionError()

    account_record = await find_account_record(account_id, date.strip())

    account_record.bank_funding = account_record.bank_funding + funding_amount
    account_record.principle = account_record.principle + funding_amount
    account_record.total_assets = account_record.total_assets + funding_amount
    if account_record.total_assets > 0:
        account_record.stock_position = account_record.total_stock_value / account_record.total_assets
    else:
        account_record.stock_position = 0
    await account_record.update()

    bank_funding_change = AccountAssetChange(
        account_id=account_id,
        change_amount=funding_amount,
        add_or_minus=True,
        security_or_bank=False,
        date=date)

    await bank_funding_change.save()

    return accounts[0]

@asyncio.coroutine
@post('/api/minus_bank_funding')
async def api_minus_bank_funding(request, *, funding_amount, date, account_id):
    must_log_in(request)
    try:
        funding_amount = float(funding_amount)
    except ValueError as e:
        raise APIValueError('funding_amount', '金额填写不正确')
    if funding_amount <=  0:
        raise APIValueError('funding_amount', '金额必须大于0')
    if date is None:
        raise APIValueError('date', '日期不能为空')
    if date.strip() == '':
        raise APIValueError('date', '请选择日期')
    if date.strip() > today():
        raise APIValueError('date', '日期不能晚于今天')

    accounts = await Account.findAll('user_id=? and id=?', [request.__user__.id, account_id])
    if len(accounts) <=0:
        raise APIPermissionError()

    account_record = await find_account_record(account_id, date.strip())

    if (account_record.bank_funding < funding_amount):
        raise APIValueError('funding_amount', '金额不足')

    account_record.bank_funding = account_record.bank_funding - funding_amount
    account_record.principle = account_record.principle - funding_amount
    account_record.total_assets = account_record.total_assets - funding_amount
    if account_record.total_assets > 0:
        account_record.stock_position = account_record.total_stock_value / account_record.total_assets
    else:
        account_record.stock_position = 0
    await account_record.update()

    bank_funding_change = AccountAssetChange(
        account_id=account_id,
        change_amount=funding_amount,
        add_or_minus=False,
        security_or_bank=False,
        date=date)

    await bank_funding_change.save()

    return accounts[0]