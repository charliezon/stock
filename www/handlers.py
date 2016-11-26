#!/usr/bin/env python3
# -*- coding: utf-8 -*-

__author__ = 'Chaoliang Zhong'

' url handlers '

import re, time, json, logging, hashlib, base64, asyncio, datetime, random

from datetime import timedelta
from aiohttp import web
from coroweb import get, post
from apis import APIValueError, APIResourceNotFoundError, APIError, APIPermissionError

from models import User, Account, AccountRecord, StockHoldRecord, StockTradeRecord, AccountAssetChange, next_id, today, convert_date
from config import configs
from stock_info import get_current_price, compute_fee, get_sell_price, get_stock_via_name, get_stock_via_code

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

@get('/test')
def test(request):
    return {
        '__template__': 'test.html'
    }

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

@asyncio.coroutine
@get('/account/create')
async def create_account(request):
    if not has_logged_in(request):
        return web.HTTPFound('/signin')
    all_accounts = await Account.findAll('user_id=?', [request.__user__.id])
    return {
        '__template__': 'create_account.html',
        'accounts': all_accounts,
        'action': '/api/accounts'
    }

@asyncio.coroutine
@get('/account/advanced/create')
async def advanced_create_account(request):
    if not has_logged_in(request):
        return web.HTTPFound('/signin')
    all_accounts = await Account.findAll('user_id=?', [request.__user__.id])
    return {
        '__template__': 'advanced_create_account.html',
        'accounts': all_accounts,
        'action': '/api/advanced/accounts'
    }

@asyncio.coroutine
@get('/account/edit/')
async def edit_account_1(request):
    return web.HTTPFound('/')

@asyncio.coroutine
@get('/account/edit')
async def edit_account_2(request):
    return web.HTTPFound('/')

@asyncio.coroutine
@get('/account/edit/{id}')
async def edit_account(request, *, id):
    if not has_logged_in(request):
        return web.HTTPFound('/signin')
    accounts = await Account.findAll('id=? and user_id=?', [id, request.__user__.id])
    if len(accounts)>0:
        all_accounts = await Account.findAll('user_id=?', [request.__user__.id])
        return {
            '__template__': 'edit_account.html',
            'accounts': all_accounts,
            'account': accounts[0],
            'action': '/api/modify/account'
        }
    else:
        return web.HTTPFound('/')

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
    account = await Account.find(account_id)
    if not account:
        raise APIPermissionError()
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
                float_profit_lost = 0
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
                    if not new_stock.stock_sell_price:
                        new_stock.stock_sell_price = get_sell_price(new_stock.stock_code, new_stock.stock_buy_date)
                    total_stock_value = total_stock_value + new_stock.stock_amount * new_stock.stock_current_price
                    float_profit_lost = float_profit_lost + (new_stock.stock_current_price-new_stock.stock_buy_price)*new_stock.stock_amount - compute_fee(True, account.commission_rate, new_stock.stock_code, new_stock.stock_buy_price, new_stock.stock_amount)
                    await new_stock.save()
                account_record.total_stock_value = total_stock_value
                account_record.total_assets = (int((account_record.security_funding + account_record.bank_funding + account_record.total_stock_value)*100))/100
                account_record.total_profit = (int((account_record.total_assets - account_record.principle)*100))/100
                account_record.stock_position = (int(account_record.total_stock_value * 10000 / account_record.total_assets))/100
                account_record.float_profit_lost = (int(float_profit_lost*100))/100
                await account_record.update()
        except Error as e:
            raise APIPermissionError()
    else:
        account_record = all_account_records[0]
        stocks = await StockHoldRecord.findAll('account_record_id=?', [account_record.id])
        if len(stocks) > 0:
            total_stock_value = 0
            float_profit_lost = 0
            for stock in stocks:
                current_price = get_current_price(stock.stock_code, date)
                if current_price:
                    stock.stock_current_price = current_price
                if not stock.stock_sell_price:
                    stock.stock_sell_price = get_sell_price(stock.stock_code, stock.stock_buy_date)
                total_stock_value = total_stock_value + stock.stock_amount * stock.stock_current_price
                float_profit_lost = float_profit_lost + (stock.stock_current_price-stock.stock_buy_price)*stock.stock_amount - compute_fee(True, account.commission_rate, stock.stock_code, stock.stock_buy_price, stock.stock_amount)
                await stock.update()
            account_record.total_stock_value = total_stock_value
            account_record.total_assets = (int((account_record.security_funding + account_record.bank_funding + account_record.total_stock_value)*100))/100
            account_record.total_profit = (int((account_record.total_assets - account_record.principle)*100))/100
            account_record.stock_position = (int(account_record.total_stock_value * 10000 / account_record.total_assets))/100
            account_record.float_profit_lost = (int(float_profit_lost*100))/100
            await account_record.update()
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
    account_records = await AccountRecord.findAll('account_id=?', [account.id], orderBy='date desc')
    most_recent_account_record = False
    advices = []
    if len(account_records)>0:
        most_recent_account_record = account_records[0]
        stocks = await StockHoldRecord.findAll('account_record_id=?', [most_recent_account_record.id])
        if len(stocks) > 0:
            for stock in stocks:
                d = convert_date(stock.stock_buy_date) + timedelta(days=31)
                if d < datetime.datetime.today():
                    advices.append('收盘前卖出'+stock.stock_name+str(stock.stock_amount)+'股')
                else:
                    d_str = d.strftime("%Y-%m-%d")
                    advices.append(d_str+'前以'+str(stock.stock_sell_price)+'元卖出'+stock.stock_name+str(stock.stock_amount)+'股')
    if account.success_times + account.fail_times==0:
        account.success_ratio = 0
    else:
        account.success_ratio = int(account.success_times*10000/(account.success_times + account.fail_times))/100

    stock_trades = await StockTradeRecord.findAll('account_id=?', [account.id])

    all_account_records_amount = len(account_records)
    all_stock_trades_amount = len(stock_trades)

    return {
        '__template__': 'account.html',
        'account': account,
        'accounts': all_accounts,
        'most_recent_account_record': most_recent_account_record,
        'advices': advices,
        'buy_action': '/api/buy',
        'sell_action': '/api/sell',
        'add_bank_funding_action' : '/api/add_bank_funding',
        'minus_bank_funding_action' : '/api/minus_bank_funding',
        'add_security_funding_action' : '/api/add_security_funding',
        'minus_security_funding_action' : '/api/minus_security_funding',
        'modify_security_funding_action' : '/api/modify_security_funding',
        'up_to_date_action' : '/api/up_to_date',
        'account_record_items_on_page' : configs.stock.account_record_items_on_page,
        'stock_trade_items_on_page' : configs.stock.stock_trade_items_on_page,
        'all_account_records_amount': all_account_records_amount,
        'all_stock_trades_amount': all_stock_trades_amount,
        'refresh_interval': configs.stock.refresh_interval*60000
    }

@asyncio.coroutine
@get('/account_records/{account_id}/{page}')
async def get_account_records(request, *, account_id, page):
    must_log_in(request)
    try:
        page = int(page)
    except ValueError as e:
        raise APIPermissionError()
    accounts = await Account.findAll('id=? and user_id=?', [account_id, request.__user__.id])
    all_accounts = await Account.findAll('user_id=?', [request.__user__.id])
    if (len(accounts) > 0):
        account = accounts[0]
    elif (len(all_accounts) > 0):
        account = all_accounts[0]
    else:
        raise APIPermissionError()
    account_records = await AccountRecord.findAll('account_id=?', [account.id], orderBy='date desc', limit=((page-1)*configs.stock.account_record_items_on_page, configs.stock.account_record_items_on_page))
    if len(account_records)>0:
        max_amount = 0
        for account_record in account_records:
            stock_hold_records = await StockHoldRecord.findAll('account_record_id=?', [account_record.id], orderBy='stock_buy_date')
            if len(stock_hold_records)>0:
                account_record.stock_hold_records = stock_hold_records
                if len(stock_hold_records)>max_amount:
                    max_amount = len(stock_hold_records)
            else:
                account_record.stock_hold_records = []
        for account_record in account_records:
            for x in range(max_amount-len(account_record.stock_hold_records)):
                account_record.stock_hold_records.append({'stock_name':'-', 'stock_amount':0, 'stock_current_price':0, 'stock_sell_price':0})

    return {
        '__template__': 'account_records.html',
        'account_records': account_records
    }

@asyncio.coroutine
@get('/account_record/{account_id}/{date}/{stock_amount}')
async def get_account_record(request, *, account_id, date, stock_amount):
    must_log_in(request)
    try:
        stock_amount = int(stock_amount)
    except ValueError as e:
        raise APIPermissionError()
    accounts = await Account.findAll('id=? and user_id=?', [account_id, request.__user__.id])
    if (len(accounts) > 0):
        account = accounts[0]
    else:
        raise APIPermissionError()
    account_records = await AccountRecord.findAll('account_id=? and date=?', [account.id, date])
    if len(account_records)>0:
        account_record = account_records[0]
        stock_hold_records = await StockHoldRecord.findAll('account_record_id=?', [account_record.id], orderBy='stock_buy_date')
        if len(stock_hold_records)>0:
            price_update = False
            float_profit_lost = 0
            total_stock_value = 0
            for stock in stock_hold_records:
                # TODO 改成从数据库读取
                current_price = get_current_price(stock.stock_code, date)
                if current_price:
                    stock.stock_current_price = current_price
                    #stock.stock_current_price = int(random.uniform(1, 100)*100)/100
                    await stock.update()
                    price_update = True
                float_profit_lost = float_profit_lost + (stock.stock_current_price-stock.stock_buy_price)*stock.stock_amount - compute_fee(True, account.commission_rate, stock.stock_code, stock.stock_buy_price, stock.stock_amount)
                total_stock_value = total_stock_value + stock.stock_current_price*stock.stock_amount
            if price_update:
                account_record.float_profit_lost = (int(float_profit_lost*100))/100
                account_record.total_stock_value = (int(total_stock_value*100))/100
                account_record.total_assets = (int((account_record.total_stock_value + account_record.security_funding + account_record.bank_funding)*100))/100
                account_record.total_profit = (int((account_record.total_assets - account_record.principle)*100))/100
                account_record.stock_position = (int(account_record.total_stock_value * 10000 / account_record.total_assets))/100
                rows = await account_record.update()
            account_record.stock_hold_records = stock_hold_records
        else:
            account_record.stock_hold_records = []
        for x in range(stock_amount-len(account_record.stock_hold_records)):
            account_record.stock_hold_records.append({'stock_name':'-', 'stock_amount':0, 'stock_current_price':0, 'stock_sell_price':0})
    else:
        raise APIPermissionError()
    return {
        '__template__': 'account_record.html',
        'account_record': account_record
    }

@asyncio.coroutine
@get('/stock_trades/{account_id}/{page}')
async def get_stock_trades(request, *, account_id, page):
    must_log_in(request)
    try:
        page = int(page)
    except ValueError as e:
        raise APIPermissionError()
    accounts = await Account.findAll('id=? and user_id=?', [account_id, request.__user__.id])
    all_accounts = await Account.findAll('user_id=?', [request.__user__.id])
    if (len(accounts) > 0):
        account = accounts[0]
    elif (len(all_accounts) > 0):
        account = all_accounts[0]
    else:
        raise APIPermissionError()
    stock_trades = await StockTradeRecord.findAll('account_id=?', [account.id], orderBy='stock_date desc', limit=((page-1)*configs.stock.stock_trade_items_on_page, configs.stock.stock_trade_items_on_page))

    return {
        '__template__': 'stock_trades.html',
        'stock_trades': stock_trades
    }


@asyncio.coroutine
@get('/api/accounts/{id}')
async def api_get_account(request, *, id):
    must_log_in(request)
    account = await Account.find(id)
    return account

@asyncio.coroutine
@get('/api/total_assets')
async def api_get_total_assets(request, *, account_id):
    must_log_in(request)
    account = await Account.find(account_id)
    if account:
        dates = []
        data = []
        all_account_records = await AccountRecord.findAll('account_id=?', [account_id], orderBy='date')
        if len(all_account_records)>0:
            min_value = all_account_records[0].total_assets
            max_value = all_account_records[0].total_assets
            for record in all_account_records:
                dates.append(record.date)
                data.append(record.total_assets)
                if record.total_assets>max_value:
                    max_value = record.total_assets
                if record.total_assets<min_value:
                    min_value = record.total_assets
            return dict(dates=dates, data=data, max=max_value, min=min_value)
        else:
            raise APIPermissionError()
    else:
        raise APIPermissionError()

@asyncio.coroutine
@get('/api/total_profit')
async def api_get_total_profit(request, *, account_id):
    must_log_in(request)
    account = await Account.find(account_id)
    if account:
        dates = []
        data = []
        all_account_records = await AccountRecord.findAll('account_id=?', [account_id], orderBy='date')
        if len(all_account_records)>0:
            min_value = all_account_records[0].total_profit
            max_value = all_account_records[0].total_profit
            for record in all_account_records:
                dates.append(record.date)
                data.append(record.total_profit)
                if record.total_profit>max_value:
                    max_value = record.total_profit
                if record.total_profit<min_value:
                    min_value = record.total_profit
            return dict(dates=dates, data=data, max=max_value, min=min_value)
        else:
            raise APIPermissionError()
    else:
        raise APIPermissionError()

@asyncio.coroutine
@post('/api/modify/account')
async def api_modify_account(request, *, id, name, commission_rate):
    must_log_in(request)
    account = await Account.find(id)
    if not account:
        raise APIValueError('name', '账户不存在')
    if account.user_id != request.__user__.id:
        raise APIValueError('name', '没有操作该账户的权限')
    if not name or not name.strip():
        raise APIValueError('name', '账户名称不能为空')
    accounts = await Account.findAll('name=?', [name.strip()])
    if len(accounts) > 0:
        for a in accounts:
            if a.id != id:
                raise APIValueError('name', '账户名称已被用')
    try:
        commission_rate = float(commission_rate)
    except ValueError as e:
        raise APIValueError('commission_rate', '手续费率填写不正确')
    if commission_rate < 0:
        raise APIValueError('commission_rate', '手续费率不能小于0')
    account.name = name.strip()
    account.commission_rate = commission_rate
    await account.update()
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
    if commission_rate < 0:
        raise APIValueError('commission_rate', '手续费率不能小于0')
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
    if commission_rate < 0:
        raise APIValueError('commission_rate', '手续费率不能小于0')
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
    if (not stock_name or not stock_name.strip()) and (not stock_code or not stock_code.strip()):
        raise APIValueError('stock_name', '股票名称和代码不能都为空')
    if stock_name and stock_name.strip():
        stock_name = stock_name.strip()
        stock_inf = get_stock_via_name(stock_name)
        if not stock_inf:
            raise APIValueError('stock_name', '出错了')
        if len(stock_inf)<1:
            raise APIValueError('stock_name', '股票不存在')
        elif len(stock_inf)>1:
            raise APIValueError('stock_name', '股票不唯一')
        stock_code = stock_inf[0]['stock_code']
    elif stock_code and stock_code.strip():
        stock_code = stock_code.strip()
        stock_inf = get_stock_via_code(stock_code)
        if not stock_inf:
            raise APIValueError('stock_code', '出错了')
        if len(stock_inf)<1:
            raise APIValueError('stock_code', '股票不存在')
        elif len(stock_inf)>1:
            raise APIValueError('stock_code', '股票不唯一')
        stock_name = stock_inf[0]['stock_name']
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
    date = date.strip()
    if date > today():
        raise APIValueError('date', '日期不能晚于今天')

    accounts = await Account.findAll('user_id=? and id=?', [request.__user__.id, account_id])
    if len(accounts) <=0:
        raise APIPermissionError()

    account_record = await find_account_record(account_id, date)

    fee = compute_fee(True, accounts[0].commission_rate, stock_code, stock_price, stock_amount)
    money = stock_amount * stock_price + fee
    if money > account_record.security_funding:
        raise APIValueError('stock_name', '股票买入金额（'+str(money)+'）超过可用银证资金（'+str(account_record.security_funding)+'）')

    account_record.security_funding = (int((account_record.security_funding - money)*100))/100
    current_price = get_current_price(stock_code, date)
    account_record.total_stock_value = (int((account_record.total_stock_value + stock_amount*current_price)*100))/100
    account_record.total_assets = (int((account_record.total_stock_value + account_record.bank_funding + account_record.security_funding)*100))/100
    if account_record.total_assets >0:
        account_record.stock_position = (int(account_record.total_stock_value * 10000 / account_record.total_assets))/100
    else:
        account_record.stock_position = 0
    account_record.total_profit = (int((account_record.total_assets - account_record.principle)*100))/100

    sell_price = get_sell_price(stock_code, date)

    exist_stocks = await StockHoldRecord.findAll('account_record_id=? and stock_code=?', [account_record.id, stock_code])
    if len(exist_stocks) > 0:
        exist_stocks[0].stock_buy_price = (exist_stocks[0].stock_buy_price*exist_stocks[0].stock_amount + stock_price*stock_amount)/(exist_stocks[0].stock_amount + stock_amount)
        exist_stocks[0].stock_amount = exist_stocks[0].stock_amount + stock_amount
        exist_stocks[0].stock_sell_price = sell_price
        exist_stocks[0].stock_buy_date = date
        exist_stocks[0].stock_current_price=current_price
        await exist_stocks[0].update()
    else:
        new_stock = StockHoldRecord(
            account_record_id=account_record.id,
            stock_code=stock_code,
            stock_name=stock_name,
            stock_amount=stock_amount,
            stock_current_price=current_price,
            stock_buy_price=stock_price,
            stock_sell_price=sell_price,
            stock_buy_date=date)
        await new_stock.save()

    float_profit_lost = 0
    stocks = await StockHoldRecord.findAll('account_record_id=?', [account_record.id])
    for stock in stocks:
        float_profit_lost = float_profit_lost + (stock.stock_current_price-stock.stock_buy_price)*stock.stock_amount - compute_fee(True, accounts[0].commission_rate, stock.stock_code, stock.stock_buy_price, stock.stock_amount)
    
    account_record.float_profit_lost = (int(float_profit_lost*100))/100

    await account_record.update()

    stock_trade = StockTradeRecord(
        account_id=accounts[0].id,
        stock_code=stock_code,
        stock_name=stock_name,
        stock_amount=stock_amount,
        stock_price=stock_price,
        stock_operation=True,
        trade_series='0',
        stock_date=date)
    await stock_trade.save()
    
    return accounts[0]

@asyncio.coroutine
@post('/api/sell')
async def api_sell(request, *, stock_name, stock_code, stock_price, stock_amount, date, account_id):
    must_log_in(request)
    if (not stock_name or not stock_name.strip()) and (not stock_code or not stock_code.strip()):
        raise APIValueError('stock_name', '股票名称和代码不能都为空')
    if stock_name and stock_name.strip():
        stock_name = stock_name.strip()
        stock_inf = get_stock_via_name(stock_name)
        if not stock_inf:
            raise APIValueError('stock_name', '出错了')
        if len(stock_inf)<1:
            raise APIValueError('stock_name', '股票不存在')
        elif len(stock_inf)>1:
            raise APIValueError('stock_name', '股票不唯一')
        stock_code = stock_inf[0]['stock_code']
    elif stock_code and stock_code.strip():
        stock_code = stock_code.strip()
        stock_inf = get_stock_via_code(stock_code)
        if not stock_inf:
            raise APIValueError('stock_code', '出错了')
        if len(stock_inf)<1:
            raise APIValueError('stock_code', '股票不存在')
        elif len(stock_inf)>1:
            raise APIValueError('stock_code', '股票不唯一')
        stock_name = stock_inf[0]['stock_name']
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
    date = date.strip()
    if date > today():
        raise APIValueError('date', '日期不能晚于今天')

    accounts = await Account.findAll('user_id=? and id=?', [request.__user__.id, account_id])
    if len(accounts) <=0:
        raise APIPermissionError()
    account_record = await find_account_record(account_id, date)
    exist_stocks = await StockHoldRecord.findAll('account_record_id=? and stock_code=?', [account_record.id, stock_code])
    if len(exist_stocks) <= 0 or exist_stocks[0].stock_amount < stock_amount:
        raise APIValueError('stock_amount', '股票数量不足')

    fee = compute_fee(False, accounts[0].commission_rate, stock_code, stock_price, stock_amount)

    account_record.security_funding = (int((account_record.security_funding + stock_price*stock_amount - fee)*100))/100
    account_record.total_stock_value = (int((account_record.total_stock_value - stock_amount*exist_stocks[0].stock_current_price)*100))/100
    account_record.total_assets = (int((account_record.total_stock_value + account_record.bank_funding + account_record.security_funding)*100))/100
    if account_record.total_assets >0:
        account_record.stock_position = (int(account_record.total_stock_value * 10000 / account_record.total_assets))/100
    else:
        account_record.stock_position = 0
    account_record.total_profit = (int((account_record.total_assets - account_record.principle)*100))/100

    stock_trade = StockTradeRecord(
        account_id=accounts[0].id,
        stock_code=stock_code,
        stock_name=stock_name,
        stock_amount=stock_amount,
        stock_price=stock_price,
        stock_operation=False,
        trade_series='0',
        stock_date=date)
    rows = await stock_trade.save()
    if rows != 1:
        raise APIValueError('stock_name', '卖出失败')

    if stock_amount == exist_stocks[0].stock_amount:
        buy_date = exist_stocks[0].stock_buy_date
        trade_series = exist_stocks[0].id
        rows = await exist_stocks[0].remove()
        if rows != 1:
            raise APIValueError('stock_name', '卖出失败')
        stock_trades = await StockTradeRecord.findAll('account_id=? and stock_code=? and stock_date>=? and trade_series=?', [accounts[0].id, stock_code, buy_date, '0'])
        profit = 0
        for trade in stock_trades:
            if trade.stock_operation:
                profit = profit - trade.stock_amount*trade.stock_price - compute_fee(True, accounts[0].commission_rate, trade.stock_code, trade.stock_price, trade.stock_amount)
            else:
                profit = profit + trade.stock_amount*trade.stock_price - compute_fee(False, accounts[0].commission_rate, trade.stock_code, trade.stock_price, trade.stock_amount)
            trade.trade_series = trade_series
            await trade.update()
        if profit>0:
            accounts[0].success_times = accounts[0].success_times + 1;
        else:
            accounts[0].fail_times = accounts[0].fail_times + 1;
        await accounts[0].update()
    else:
        exist_stocks[0].stock_amount = exist_stocks[0].stock_amount - stock_amount
        await exist_stocks[0].update()

    float_profit_lost = 0
    stocks = await StockHoldRecord.findAll('account_record_id=?', [account_record.id])
    for stock in stocks:
        float_profit_lost = float_profit_lost + (stock.stock_current_price-stock.stock_buy_price)*stock.stock_amount - compute_fee(True, accounts[0].commission_rate, stock.stock_code, stock.stock_buy_price, stock.stock_amount)
    
    account_record.float_profit_lost = (int(float_profit_lost*100))/100

    await account_record.update()

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

    account_record.bank_funding = (int((account_record.bank_funding - funding_amount)*100))/100
    account_record.security_funding = (int((account_record.security_funding + funding_amount)*100))/100
    await account_record.update()

    security_funding_change = AccountAssetChange(
        account_id=account_id,
        change_amount=funding_amount,
        operation=1,
        security_or_bank=True,
        date=date)

    await security_funding_change.save()

    bank_funding_change = AccountAssetChange(
        account_id=account_id,
        change_amount=funding_amount,
        operation=0,
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

    account_record.bank_funding = (int((account_record.bank_funding + funding_amount)*100))/100
    account_record.security_funding = (int((account_record.security_funding - funding_amount)*100))/100
    await account_record.update()

    security_funding_change = AccountAssetChange(
        account_id=account_id,
        change_amount=funding_amount,
        operation=0,
        security_or_bank=True,
        date=date)

    await security_funding_change.save()

    bank_funding_change = AccountAssetChange(
        account_id=account_id,
        change_amount=funding_amount,
        operation=1,
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

    account_record.bank_funding = (int((account_record.bank_funding + funding_amount)*100))/100
    account_record.principle = (int((account_record.principle + funding_amount)*100))/100
    account_record.total_assets = (int((account_record.total_assets + funding_amount)*100))/100
    if account_record.total_assets > 0:
        account_record.stock_position = (int(account_record.total_stock_value * 10000 / account_record.total_assets))/100
    else:
        account_record.stock_position = 0
    await account_record.update()

    bank_funding_change = AccountAssetChange(
        account_id=account_id,
        change_amount=funding_amount,
        operation=1,
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

    account_record.bank_funding = (int((account_record.bank_funding - funding_amount)*100))/100
    account_record.principle = (int((account_record.principle - funding_amount)*100))/100
    account_record.total_assets = (int((account_record.total_assets - funding_amount)*100))/100
    if account_record.total_assets > 0:
        account_record.stock_position = (int(account_record.total_stock_value * 10000 / account_record.total_assets))/100
    else:
        account_record.stock_position = 0
    await account_record.update()

    bank_funding_change = AccountAssetChange(
        account_id=account_id,
        change_amount=funding_amount,
        operation=0,
        security_or_bank=False,
        date=date)

    await bank_funding_change.save()

    return accounts[0]

@asyncio.coroutine
@post('/api/modify_security_funding')
async def api_modify_security_funding(request, *, funding_amount, date, account_id):
    must_log_in(request)
    try:
        funding_amount = float(funding_amount)
    except ValueError as e:
        raise APIValueError('funding_amount', '金额填写不正确')
    if funding_amount < 0:
        raise APIValueError('funding_amount', '金额必须大于等于0')
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
    account_record.security_funding = funding_amount

    account_record.total_assets = (int((account_record.total_stock_value + account_record.bank_funding + account_record.security_funding)*100))/100
    if account_record.total_assets >0:
        account_record.stock_position = (int(account_record.total_stock_value * 10000 / account_record.total_assets))/100
    else:
        account_record.stock_position = 0
    account_record.total_profit = (int((account_record.total_assets - account_record.principle)*100))/100

    await account_record.update()

    security_funding_change = AccountAssetChange(
        account_id=account_id,
        change_amount=funding_amount,
        operation=2,
        security_or_bank=True,
        date=date)

    await security_funding_change.save()

    return accounts[0]

@asyncio.coroutine
@post('/api/up_to_date')
async def api_up_to_date(request, *, date, account_id):
    must_log_in(request)
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

    return accounts[0]

@asyncio.coroutine
@get('/param_statistical')
async def do_param_statistical(request):
    if not has_logged_in(request):
        return web.HTTPFound('/signin')
    check_admin(request)

    all_accounts = await Account.findAll('user_id=?', [request.__user__.id])
    return {
        '__template__': 'param_statistical.html',
        'accounts': all_accounts,
        'action': ''
    }