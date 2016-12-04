#!/usr/bin/env python3
# -*- coding: utf-8 -*-

__author__ = 'Chaoliang Zhong'

' url handlers '

import re, time, json, logging, hashlib, base64, asyncio, datetime, random

from datetime import timedelta
from aiohttp import web
from coroweb import get, post
from apis import APIValueError, APIResourceNotFoundError, APIError, APIPermissionError

from models import User, Account, AccountRecord, StockHoldRecord, StockTradeRecord, AccountAssetChange, DailyParam, next_id, today, convert_date, round_float
from config import configs
from stock_info import get_current_price, compute_fee, get_sell_price, get_stock_via_name, get_stock_via_code, get_shanghai_index_info, find_open_price_with_code

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
            logging.info("-------------------------------1")
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
                account_record.total_assets = round_float(account_record.security_funding + account_record.bank_funding + account_record.total_stock_value)
                account_record.total_profit = round_float(account_record.total_assets - account_record.principle)
                account_record.stock_position = round_float(account_record.total_stock_value * 100 / account_record.total_assets)
                account_record.float_profit_lost = round_float(float_profit_lost)
                await account_record.update()
        except Error as e:
            raise APIPermissionError()
    else:
        logging.info("-------------------------------2")
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
            account_record.total_assets = round_float(account_record.security_funding + account_record.bank_funding + account_record.total_stock_value)
            account_record.total_profit = round_float(account_record.total_assets - account_record.principle)
            account_record.stock_position = round_float(account_record.total_stock_value * 100 / account_record.total_assets)
            account_record.float_profit_lost = round_float(float_profit_lost)
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

    dp = await DailyParam.findAll(orderBy='date desc', limit=1)
    if len(dp)>0:
        dadieweizhidie = False
        dp1 = await DailyParam.findAll('increase_range<?', [-0.015], orderBy='date desc', limit=1)
        if len(dp1)>0:
            dp2 = await DailyParam.findAll('date>? and increase_range>?', [dp1[0].date, 0], orderBy='date desc', limit=1)
            if len(dp2)==0:
                dadieweizhidie = True 
        logging.info('大跌未止跌：'+str(dadieweizhidie))
        # 最大仓位
        max_position = 0
        if dp[0].stock_market_status == 0:
            max_position = 0.25
            if not dp[0].big_fall_after_multi_bank_iron:
                max_position = 0.125
        if dp[0].stock_market_status == 1 or dp[0].stock_market_status == 2:
            max_position = 1
            if dadieweizhidie or not dp[0].big_fall_after_multi_bank_iron:
                max_position = 0.5
        logging.info('最大仓位：'+str(max_position))
        # 清仓
        clear = dp[0].shanghai_break_twenty_days_line or dp[0].shenzhen_break_twenty_days_line or dp[0].shanghai_break_twenty_days_line_for_two_days or dp[0].shenzhen_break_twenty_days_line_for_two_days or (dp[0].run_stock_ratio>0.02484 and dp[0].pursuit_stock_ratio<0.03)
        logging.info('清仓：'+str(clear))

        dp3 = await DailyParam.findAll(orderBy='date desc', limit=5)
        flag1 = False
        for d in dp3:
            if d.run_stock_ratio > 0.02484:
                flag1 = True
                break
        dp4 = await DailyParam.findAll(orderBy='date desc', limit=2)
        flag2 = False
        for d in dp4:
            if d.pursuit_kdj_die_stock_ratio>=0.5:
                flag2 = True
                break

        # 不能买
        cant_buy = dadieweizhidie or dp[0].pursuit_stock_ratio<0.0036 or dp[0].strong_pursuit_stock_ratio<0.0018 or flag1 or flag2
        logging.info(str(dp[0].shanghai_break_twenty_days_line_for_two_days))
        logging.info(str(dp[0].shenzhen_break_twenty_days_line_for_two_days))
        logging.info(str(dadieweizhidie))
        logging.info(str(dp[0].pursuit_stock_ratio))
        logging.info(str(dp[0].strong_pursuit_stock_ratio))
        logging.info(str(flag1))
        logging.info(str(flag2))
        logging.info('不能买：'+str(cant_buy))

        # 方式1买入仓位
        method1_buy_position = 1/4
        if dp[0].stock_market_status == 0:
            if dadieweizhidie:
                method1_buy_position = method1_buy_position/4
            elif not dp[0].big_fall_after_multi_bank_iron:
                method1_buy_position = method1_buy_position/2
        if dp[0].stock_market_status == 1:
            if dadieweizhidie:
                method1_buy_position = method1_buy_position/4
        if dp[0].stock_market_status == 2:
            if dadieweizhidie:
                method1_buy_position = method1_buy_position/4
        logging.info('方式1买入仓位：'+str(method1_buy_position))
        # 方式2买入仓位
        method2_buy_position = 1/16
        if dp[0].stock_market_status == 0:
            if dadieweizhidie:
                method2_buy_position = 0
            elif not dp[0].big_fall_after_multi_bank_iron:
                method2_buy_position = method2_buy_position/2
        if dp[0].stock_market_status == 1:
            if dadieweizhidie:
                method2_buy_position = 0
        if dp[0].stock_market_status == 2:
            method2_buy_position = 1/4
            if dadieweizhidie:
                method2_buy_position = 0
        logging.info('方式2买入仓位：'+str(method2_buy_position))

    advices = []
    current_position = 0
    if len(account_records)>0:
        # 当前仓位
        current_position = account_records[0].stock_position / 100
        most_recent_account_record = account_records[0]    
    if clear:
        if current_position > 0:
            advices.append('<span style="color:red"><strong>今日务必择机清仓！</strong></span>')
    else:
        if len(account_records)>0:
            if current_position >= max_position:
                cant_buy = True
                logging.info('current_position：'+str(current_position))
                logging.info('max_position'+str(max_position))
                logging.info('不能买：'+str(cant_buy))
            stocks = await StockHoldRecord.findAll('account_record_id=?', [most_recent_account_record.id])
            if len(stocks) > 0:
                for stock in stocks:
                    d = convert_date(stock.stock_buy_date) + timedelta(days=31)
                    if d < datetime.datetime.today():
                        advices.append('收盘前<span class="uk-badge uk-badge-danger">卖出</span>'+stock.stock_name+str(stock.stock_amount)+'股')
                    else:
                        d_str = d.strftime("%Y-%m-%d")
                        advices.append(d_str+'前以'+str(stock.stock_sell_price)+'元<span class="uk-badge uk-badge-danger">卖出</span>'+stock.stock_name+str(stock.stock_amount)+'股')
        if not cant_buy:
            if dp[0].method_1:
                stocks = get_stock_via_name(dp[0].method_1)
                buy_position = max_position - current_position if method1_buy_position>max_position - current_position else method1_buy_position
                if not stocks or len(stocks)!=1:
                    advices.append('以开盘价<span class="uk-badge uk-badge-success">买入</span>'+dp[0].method_1+str(round_float(buy_position*100))+'%仓')
                else:
                    stock_code = stocks[0].stock_code
                    price = find_open_price_with_code(stock_code)
                    if not price:
                        price = get_current_price(stock_code, today())
                    if price:
                        advices.append('以开盘价<span class="uk-badge uk-badge-success">买入</span>'+dp[0].method_1+str(int(round_float(most_recent_account_record.total_assets*buy_position/price/100, 0)*100))+'股')
                    else:
                        advices.append('以开盘价<span class="uk-badge uk-badge-success">买入</span>'+dp[0].method_1+str(round_float(buy_position*100))+'%仓')
            elif dp[0].method_2:
                stocks = get_stock_via_name(dp[0].method_2)
                buy_position = max_position - current_position if method2_buy_position>max_position - current_position else method2_buy_position
                if not stocks or len(stocks)!=1:
                    advices.append('以开盘价<span class="uk-badge uk-badge-success">买入</span>'+dp[0].method_2+str(round_float(buy_position*100))+'%仓')
                else:
                    stock_code = stocks[0]['stock_code']
                    price = find_open_price_with_code(stock_code)
                    if not price:
                        price = get_current_price(stock_code, today())
                    if price:
                        advices.append('以开盘价<span class="uk-badge uk-badge-success">买入</span>'+dp[0].method_2+str(int(round_float(most_recent_account_record.total_assets*buy_position/price/100, 0)*100))+'股')
                    else:
                        advices.append('以开盘价<span class="uk-badge uk-badge-success">买入</span>'+dp[0].method_2+str(round_float(buy_position*100))+'%仓')

    if account.success_times + account.fail_times==0:
        account.success_ratio = 0
    else:
        account.success_ratio = round_float(account.success_times*100/(account.success_times + account.fail_times))

    stock_trades = await StockTradeRecord.findAll('account_id=?', [account.id])

    all_account_records_amount = len(account_records)
    logging.info('--------------------------all_account_records_amount: '+str(all_account_records_amount))
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
            dp = await DailyParam.find(account_record.date)
            account_record.stock_market_status = '-'
            if dp:
                if dp.stock_market_status == 0:
                    if dp.twenty_days_line:
                        account_record.stock_market_status = '<span class="uk-badge uk-badge-danger">熊</span><span class="uk-badge uk-badge-success">沪20上</span>'
                    else:
                        account_record.stock_market_status = '<span class="uk-badge uk-badge-danger">熊</span><span class="uk-badge uk-badge-danger">沪20下</span>'
                elif dp.stock_market_status == 1:
                    account_record.stock_market_status = '<span class="uk-badge uk-badge-warning">小牛</span>'
                else:
                    account_record.stock_market_status = '<span class="uk-badge uk-badge-success">大牛</span>'
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
                account_record.float_profit_lost = round_float(float_profit_lost)
                account_record.total_stock_value = round_float(total_stock_value)
                account_record.total_assets = round_float(account_record.total_stock_value + account_record.security_funding + account_record.bank_funding)
                account_record.total_profit = round_float(account_record.total_assets - account_record.principle)
                account_record.stock_position = round_float(account_record.total_stock_value * 100 / account_record.total_assets)
                rows = await account_record.update()
            account_record.stock_hold_records = stock_hold_records
        else:
            account_record.stock_hold_records = []
        for x in range(stock_amount-len(account_record.stock_hold_records)):
            account_record.stock_hold_records.append({'stock_name':'-', 'stock_amount':0, 'stock_current_price':0, 'stock_sell_price':0})
        dp = await DailyParam.find(account_record.date)
        account_record.stock_market_status = '-'

        if dp:
            if dp.stock_market_status == 0:
                if dp.twenty_days_line:
                    account_record.stock_market_status = '<span class="uk-badge uk-badge-danger">熊</span><span class="uk-badge uk-badge-success">沪20上</span>'
                else:
                    account_record.stock_market_status = '<span class="uk-badge uk-badge-danger">熊</span><span class="uk-badge uk-badge-danger">沪20下</span>'
            elif dp.stock_market_status == 1:
                account_record.stock_market_status = '<span class="uk-badge uk-badge-warning">小牛</span>'
            else:
                account_record.stock_market_status = '<span class="uk-badge uk-badge-success">大牛</span>'
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
        account_record = AccountRecord(date=date, account_id=account.id, stock_position=0, security_funding=0, bank_funding=round_float(initial_funding), total_stock_value=0, total_assets=round_float(initial_funding), float_profit_lost=0, total_profit=0, principle=round_float(initial_funding))
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
        account_record = AccountRecord(date=date, 
                                        account_id=account.id, 
                                        stock_position=0, 
                                        security_funding=round_float(initial_security_funding), 
                                        bank_funding=round_float(initial_bank_funding), 
                                        total_stock_value=0, 
                                        total_assets=round_float(initial_security_funding+initial_bank_funding), 
                                        float_profit_lost=0, 
                                        total_profit=round_float(initial_security_funding+initial_bank_funding-initial_funding), 
                                        principle=round_float(initial_funding))
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

    account_record.security_funding = round_float(account_record.security_funding - money)
    current_price = get_current_price(stock_code, date)
    account_record.total_stock_value = round_float(account_record.total_stock_value + stock_amount*current_price)
    account_record.total_assets = round_float(account_record.total_stock_value + account_record.bank_funding + account_record.security_funding)
    if account_record.total_assets >0:
        account_record.stock_position = round_float(account_record.total_stock_value * 100 / account_record.total_assets)
    else:
        account_record.stock_position = 0
    account_record.total_profit = round_float(account_record.total_assets - account_record.principle)

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
    
    account_record.float_profit_lost = round_float(float_profit_lost)

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

    account_record.security_funding = round_float(account_record.security_funding + stock_price*stock_amount - fee)
    account_record.total_stock_value = round_float(account_record.total_stock_value - stock_amount*exist_stocks[0].stock_current_price)
    account_record.total_assets = round_float(account_record.total_stock_value + account_record.bank_funding + account_record.security_funding)
    if account_record.total_assets >0:
        account_record.stock_position = round_float(account_record.total_stock_value * 100 / account_record.total_assets)
    else:
        account_record.stock_position = 0
    account_record.total_profit = round_float(account_record.total_assets - account_record.principle)

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
    
    account_record.float_profit_lost = round_float(float_profit_lost)

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

    account_record.bank_funding = round_float(account_record.bank_funding - funding_amount)
    account_record.security_funding = round_float(account_record.security_funding + funding_amount)
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

    account_record.bank_funding = round_float(account_record.bank_funding + funding_amount)
    account_record.security_funding = round_float(account_record.security_funding - funding_amount)
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

    account_record.bank_funding = round_float(account_record.bank_funding + funding_amount)
    account_record.principle = round_float(account_record.principle + funding_amount)
    account_record.total_assets = round_float(account_record.total_assets + funding_amount)
    if account_record.total_assets > 0:
        account_record.stock_position = round_float(account_record.total_stock_value * 100 / account_record.total_assets)
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

    account_record.bank_funding = round_float(account_record.bank_funding - funding_amount)
    account_record.principle = round_float(account_record.principle - funding_amount)
    account_record.total_assets = round_float(account_record.total_assets - funding_amount)
    if account_record.total_assets > 0:
        account_record.stock_position = round_float(account_record.total_stock_value * 100 / account_record.total_assets)
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

    account_record.total_assets = round_float(account_record.total_stock_value + account_record.bank_funding + account_record.security_funding)
    if account_record.total_assets >0:
        account_record.stock_position = round_float(account_record.total_stock_value * 100 / account_record.total_assets)
    else:
        account_record.stock_position = 0
    account_record.total_profit = round_float(account_record.total_assets - account_record.principle)

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
async def do_param_statistica_1(request):
    return await handle_param_statistical(request, today())

@asyncio.coroutine
@get('/param_statistical/')
async def do_param_statistical_2(request):
    return await handle_param_statistical(request, today())

@asyncio.coroutine
@get('/param_statistical/{date}')
async def do_param_statistical(request, *, date):
    return await handle_param_statistical(request, date)

@asyncio.coroutine
async def handle_param_statistical(request, date):
    result = await get_index_info(request, date)
    all_accounts = await Account.findAll('user_id=?', [request.__user__.id])
    dp = await DailyParam.find(date)
    if dp:
        dp.twenty_days_line = int(dp.twenty_days_line)
        dp.shanghai_break_twenty_days_line = int(dp.shanghai_break_twenty_days_line)
        dp.shanghai_break_twenty_days_line_for_two_days = int(dp.shanghai_break_twenty_days_line_for_two_days)
        dp.shenzhen_break_twenty_days_line = int(dp.shenzhen_break_twenty_days_line)
        dp.shenzhen_break_twenty_days_line_for_two_days = int(dp.shenzhen_break_twenty_days_line_for_two_days)        

    if not dp:
        dp = DailyParam()
        dp.shanghai_index = result['shanghai_index']
        dp.increase_range = result['increase_range']
        dp.three_days_average_shanghai_increase = result['three_days_average_shanghai_increase']
        dp.date = date
        dp.all_stock_amount = ''
        dp.buy_stock_amount = ''
        dp.pursuit_stock_amount = ''
        dp.iron_stock_amount = ''
        dp.bank_stock_amount = ''
        dp.strong_pursuit_stock_amount = ''
        dp.pursuit_kdj_die_stock_amount = ''
        dp.run_stock_amount = ''
        dp.method_1 = ''
        dp.method_2 = ''
        dps = await DailyParam.findAll(orderBy='date desc', limit=1)
        futures = ''
        if len(dps)>0:
            dp.futures = dps[0].futures
            dp.stock_market_status = dps[0].stock_market_status
            dp.twenty_days_line = int(dps[0].twenty_days_line)
            dp.shanghai_break_twenty_days_line = int(dps[0].shanghai_break_twenty_days_line)
            dp.shanghai_break_twenty_days_line_for_two_days = int(dps[0].shanghai_break_twenty_days_line_for_two_days)
            dp.shenzhen_break_twenty_days_line = int(dps[0].shenzhen_break_twenty_days_line)
            dp.shenzhen_break_twenty_days_line_for_two_days = int(dps[0].shenzhen_break_twenty_days_line_for_two_days)
        else:
            dp.futures = ''
            dp.stock_market_status = 0
            dp.twenty_days_line = 0
            dp.shanghai_break_twenty_days_line = 0
            dp.shanghai_break_twenty_days_line_for_two_days = 0
            dp.shenzhen_break_twenty_days_line = 0
            dp.shenzhen_break_twenty_days_line_for_two_days = 0
    return {
        '__template__': 'param_statistical.html',
        'dp': dp,
        'accounts': all_accounts,
        'action': '/api/param_statistical'
    }

@asyncio.coroutine
@post('/api/param_statistical')
async def api_param_statistical(request, *, date, shanghai_index, stock_market_status, twenty_days_line, increase_range, three_days_average_shanghai_increase, 
                                shanghai_break_twenty_days_line, shanghai_break_twenty_days_line_for_two_days, shenzhen_break_twenty_days_line,
                                shenzhen_break_twenty_days_line_for_two_days, all_stock_amount, buy_stock_amount, pursuit_stock_amount,
                                iron_stock_amount, bank_stock_amount, strong_pursuit_stock_amount, pursuit_kdj_die_stock_amount, run_stock_amount,
                                futures, method_1, method_2):
    must_log_in(request)
    check_admin(request)
    if date is None:
        raise APIValueError('date', '日期不能为空')
    if date.strip() == '':
        raise APIValueError('date', '请选择日期')
    date = date.strip()
    if date > today():
        raise APIValueError('date', '日期不能晚于今天')
    logging.info('---------------'+str(date))
    try:
        shanghai_index = float(shanghai_index)
    except ValueError as e:
        raise APIValueError('shanghai_index', '沪指指数填写不正确')
    if shanghai_index <= 0:
        raise APIValueError('shanghai_index', '沪指指数必须大于0')
    logging.info('---------------'+str(shanghai_index))
    logging.info('---------------'+str(stock_market_status))
    logging.info('---------------20 days line '+str(twenty_days_line))
    try:
        three_days_average_shanghai_increase = float(three_days_average_shanghai_increase)
    except ValueError as e:
        raise APIValueError('three_days_average_shanghai_increase', '沪指三天平均涨幅填写不正确')
    logging.info('---------------'+str(three_days_average_shanghai_increase))
    try:
        increase_range = float(increase_range)
    except ValueError as e:
        raise APIValueError('increase_range', '沪指涨幅填写不正确')
    logging.info('---------------'+str(increase_range))
    logging.info('---------------shanghai_break_twenty_days_line  '+str(shanghai_break_twenty_days_line))
    logging.info('---------------shanghai_break_twenty_days_line_for_two_days  '+str(shanghai_break_twenty_days_line_for_two_days))
    logging.info('---------------shenzhen_break_twenty_days_line  '+str(shenzhen_break_twenty_days_line))
    logging.info('---------------shenzhen_break_twenty_days_line_for_two_days  '+str(shenzhen_break_twenty_days_line_for_two_days))
    try:
        all_stock_amount = int(all_stock_amount)
    except ValueError as e:
        raise APIValueError('all_stock_amount', '总股票数填写不正确')
    if all_stock_amount<=0:
        raise APIValueError('all_stock_amount', '总股票数填写不正确')
    logging.info('---------------all_stock_amount: '+str(all_stock_amount))
    try:
        buy_stock_amount = int(buy_stock_amount)
    except ValueError as e:
        raise APIValueError('buy_stock_amount', '发出买入信号的股票数填写不正确')
    if buy_stock_amount<0:
        raise APIValueError('buy_stock_amount', '发出买入信号的股票数填写不正确')
    logging.info('---------------buy_stock_amount: '+str(buy_stock_amount))
    try:
        pursuit_stock_amount = int(pursuit_stock_amount)
    except ValueError as e:
        raise APIValueError('pursuit_stock_amount', '发出追涨信号的股票数填写不正确')
    if pursuit_stock_amount<0:
        raise APIValueError('pursuit_stock_amount', '发出追涨信号的股票数填写不正确')
    pursuit_stock_ratio=pursuit_stock_amount/all_stock_amount
    logging.info('---------------pursuit_stock_amount: '+str(pursuit_stock_amount))
    try:
        iron_stock_amount = int(iron_stock_amount)
    except ValueError as e:
        raise APIValueError('iron_stock_amount', '发出买入或追涨信号的普钢股票数填写不正确')
    if iron_stock_amount<0:
        raise APIValueError('iron_stock_amount', '发出买入或追涨信号的普钢股票数填写不正确')
    logging.info('---------------iron_stock_amount: '+str(iron_stock_amount))
    try:
        bank_stock_amount = int(bank_stock_amount)
    except ValueError as e:
        raise APIValueError('bank_stock_amount', '发出买入或追涨信号的银行股票数填写不正确')
    if bank_stock_amount<0:
        raise APIValueError('bank_stock_amount', '发出买入或追涨信号的银行股票数填写不正确')
    logging.info('---------------bank_stock_amount: '+str(bank_stock_amount))
    try:
        strong_pursuit_stock_amount = int(strong_pursuit_stock_amount)
    except ValueError as e:
        raise APIValueError('strong_pursuit_stock_amount', '发出强烈追涨信号的股票数填写不正确')
    if strong_pursuit_stock_amount<0:
        raise APIValueError('strong_pursuit_stock_amount', '发出强烈追涨信号的股票数填写不正确')
    logging.info('---------------strong_pursuit_stock_amount: '+str(strong_pursuit_stock_amount))
    try:
        pursuit_kdj_die_stock_amount = int(pursuit_kdj_die_stock_amount)
    except ValueError as e:
        raise APIValueError('pursuit_kdj_die_stock_amount', '发出追涨信号但KDJ死叉的股票数填写不正确')
    if pursuit_kdj_die_stock_amount<0:
        raise APIValueError('pursuit_kdj_die_stock_amount', '发出追涨信号但KDJ死叉的股票数填写不正确')
    logging.info('---------------pursuit_kdj_die_stock_amount: '+str(pursuit_kdj_die_stock_amount))
    try:
        run_stock_amount = int(run_stock_amount)
    except ValueError as e:
        raise APIValueError('run_stock_amount', '发出逃顶信号的股票数填写不正确')
    if run_stock_amount<0:
        raise APIValueError('run_stock_amount', '发出逃顶信号的股票数填写不正确')
    logging.info('---------------run_stock_amount: '+str(run_stock_amount))


    pursuit_kdj_die_stock_ratio = pursuit_kdj_die_stock_amount/pursuit_stock_amount if pursuit_stock_amount!=0 else 0

    big_fall_after_multi_bank_iron = False
    dps1 = await DailyParam.findAll('iron_stock_amount>? or bank_stock_amount>?', [1, 1], orderBy='date desc', limit=1)
    if len(dps1)>0:
        dps2 = await DailyParam.findAll('date>? and increase_range<=?', [dps1[0].date, -0.015])
        if len(dps2) == 0:
            big_fall_after_multi_bank_iron = False
        else:
            big_fall_after_multi_bank_iron = True

    four_days_pursuit_ratio_decrease = False
    dps3 = await DailyParam.findAll('date<=?', [date], orderBy='date desc', limit=3)
    if len(dps3) == 3:
        if (dps3[2].pursuit_stock_ratio >= 0.032 and dps3[1].pursuit_stock_ratio >= 0.032 and dps3[0].pursuit_stock_ratio < 0.032) or (dps3[1].pursuit_stock_ratio >= 0.032 and dps3[0].pursuit_stock_ratio >= 0.032 and pursuit_stock_ratio<0.032):
            four_days_pursuit_ratio_decrease = True

    dp = await DailyParam.find(date)
    if dp:
        dp.date = date
        dp.shanghai_index=shanghai_index
        dp.stock_market_status=int(stock_market_status)
        dp.twenty_days_line=True if str(twenty_days_line)=='1' else False
        dp.increase_range=increase_range
        dp.three_days_average_shanghai_increase=three_days_average_shanghai_increase
        dp.shanghai_break_twenty_days_line=True if str(shanghai_break_twenty_days_line)=='1' else False
        dp.shanghai_break_twenty_days_line_for_two_days=True if str(shanghai_break_twenty_days_line_for_two_days)=='1' else False
        dp.shenzhen_break_twenty_days_line=True if str(shenzhen_break_twenty_days_line)=='1' else False
        dp.shenzhen_break_twenty_days_line_for_two_days=True if str(shenzhen_break_twenty_days_line_for_two_days)=='1' else False
        dp.all_stock_amount=all_stock_amount
        dp.buy_stock_amount=buy_stock_amount
        dp.buy_stock_ratio=buy_stock_amount/all_stock_amount
        dp.pursuit_stock_amount=pursuit_stock_amount
        dp.pursuit_stock_ratio=pursuit_stock_amount/all_stock_amount
        dp.iron_stock_amount=iron_stock_amount
        dp.bank_stock_amount=bank_stock_amount
        dp.strong_pursuit_stock_amount=strong_pursuit_stock_amount
        dp.strong_pursuit_stock_ratio=strong_pursuit_stock_amount/all_stock_amount
        dp.pursuit_kdj_die_stock_amount=pursuit_kdj_die_stock_amount
        dp.pursuit_kdj_die_stock_ratio=pursuit_kdj_die_stock_ratio
        dp.run_stock_amount=run_stock_amount
        dp.run_stock_ratio=run_stock_amount/all_stock_amount
        dp.big_fall_after_multi_bank_iron=big_fall_after_multi_bank_iron
        dp.four_days_pursuit_ratio_decrease=four_days_pursuit_ratio_decrease
        dp.too_big_increase=(pursuit_stock_ratio>=0.03)
        dp.futures=futures
        dp.method_1=method_1
        dp.method_2=method_2
        await dp.update()
    else:
        dp = DailyParam(date=date,
                        shanghai_index=shanghai_index,
                        stock_market_status=int(stock_market_status),
                        twenty_days_line=True if str(twenty_days_line)=='1' else False,
                        increase_range=increase_range,
                        three_days_average_shanghai_increase=three_days_average_shanghai_increase,
                        shanghai_break_twenty_days_line=True if str(shanghai_break_twenty_days_line)=='1' else False,
                        shanghai_break_twenty_days_line_for_two_days=True if str(shanghai_break_twenty_days_line_for_two_days)=='1' else False,
                        shenzhen_break_twenty_days_line=True if str(shenzhen_break_twenty_days_line)=='1' else False,
                        shenzhen_break_twenty_days_line_for_two_days=True if str(shenzhen_break_twenty_days_line_for_two_days)=='1' else False,
                        all_stock_amount=all_stock_amount,
                        buy_stock_amount=buy_stock_amount,
                        buy_stock_ratio=buy_stock_amount/all_stock_amount,
                        pursuit_stock_amount=pursuit_stock_amount,
                        pursuit_stock_ratio=pursuit_stock_amount/all_stock_amount,
                        iron_stock_amount=iron_stock_amount,
                        bank_stock_amount=bank_stock_amount,
                        strong_pursuit_stock_amount=strong_pursuit_stock_amount,
                        strong_pursuit_stock_ratio=strong_pursuit_stock_amount/all_stock_amount,
                        pursuit_kdj_die_stock_amount=pursuit_kdj_die_stock_amount,
                        pursuit_kdj_die_stock_ratio=pursuit_kdj_die_stock_ratio,
                        run_stock_amount=run_stock_amount,
                        run_stock_ratio=run_stock_amount/all_stock_amount,
                        big_fall_after_multi_bank_iron=big_fall_after_multi_bank_iron,
                        four_days_pursuit_ratio_decrease=four_days_pursuit_ratio_decrease,
                        too_big_increase=(pursuit_stock_ratio>=0.03),
                        futures=futures,
                        method_1=method_1,
                        method_2=method_2)
        await dp.save()
    return dp

@asyncio.coroutine
@get('/params')
async def do_params(request):
    if not has_logged_in(request):
        return web.HTTPFound('/signin')
    check_admin(request)
    all_accounts = await Account.findAll('user_id=?', [request.__user__.id])
    dps = await DailyParam.findAll()
    return {
        '__template__': 'params.html',
        'accounts': all_accounts,
        'params_amount': len(dps),
        'param_items_on_page': configs.stock.param_items_on_page
    }

@asyncio.coroutine
@get('/params/{page}')
async def get_params(request, *, page):
    must_log_in(request)
    check_admin(request)
    try:
        page = int(page)
    except ValueError as e:
        raise APIPermissionError()
    dps = await DailyParam.findAll(orderBy='date desc', limit=((page-1)*configs.stock.param_items_on_page, configs.stock.param_items_on_page))
    if len(dps)>0:
        for dp in dps:
            if dp.stock_market_status == 0:
                if dp.twenty_days_line:
                    dp.stock_market_status = '<span class="uk-badge uk-badge-danger">熊</span><span class="uk-badge uk-badge-success">沪20上</span>'
                else:
                    dp.stock_market_status = '<span class="uk-badge uk-badge-danger">熊</span><span class="uk-badge uk-badge-danger">沪20下</span>'
            elif dp.stock_market_status == 1:
                dp.stock_market_status = '<span class="uk-badge uk-badge-warning">小牛</span>'
            else:
                dp.stock_market_status = '<span class="uk-badge uk-badge-success">大牛</span>'
            dp.twenty_days_line='<span class="uk-badge uk-badge-success">否</span>' if dp.twenty_days_line else '<span class="uk-badge uk-badge-danger">跌破</span>'
            dp.big_fall_after_multi_bank_iron='<span class="uk-badge uk-badge-success">大跌</span>' if dp.big_fall_after_multi_bank_iron else '<span class="uk-badge uk-badge-danger">否</span>'
            dp.four_days_pursuit_ratio_decrease='<span class="uk-badge uk-badge-danger">变小</span>' if dp.four_days_pursuit_ratio_decrease else '<span class="uk-badge uk-badge-success">否</span>'
            dp.shanghai_index = round_float(dp.shanghai_index)
            
            if dp.three_days_average_shanghai_increase >= 0.015:
                dp.three_days_average_shanghai_increase = '<span class="uk-badge uk-badge-danger">'+str(round_float(dp.three_days_average_shanghai_increase*100))+'%</span>'
            else:
                dp.three_days_average_shanghai_increase = '<span class="uk-badge uk-badge-success">'+str(round_float(dp.three_days_average_shanghai_increase*100))+'%</span>'

            if dp.buy_stock_amount > 0:
                dp.buy_stock_amount = '<span class="uk-badge uk-badge-danger">'+str(dp.buy_stock_amount)+'</span>'
            else:
                dp.buy_stock_amount = '<span class="uk-badge uk-badge-success">'+str(dp.buy_stock_amount)+'</span>'

            if dp.pursuit_stock_ratio > 0.03:
                dp.pursuit_stock_amount = '<span class="uk-badge uk-badge-warning">'+str(dp.pursuit_stock_amount)+'</span>'
            elif dp.pursuit_stock_ratio < 0.0036:
                dp.pursuit_stock_amount = '<span class="uk-badge uk-badge-danger">'+str(dp.pursuit_stock_amount)+'</span>'
            else:
                dp.pursuit_stock_amount = '<span class="uk-badge uk-badge-success">'+str(dp.pursuit_stock_amount)+'</span>'

            if dp.strong_pursuit_stock_ratio < 0.0018:
                dp.strong_pursuit_stock_amount = '<span class="uk-badge uk-badge-danger">'+str(dp.strong_pursuit_stock_amount)+'</span>'
            else:
                dp.strong_pursuit_stock_amount = '<span class="uk-badge uk-badge-success">'+str(dp.strong_pursuit_stock_amount)+'</span>'

            if dp.pursuit_kdj_die_stock_ratio >= 0.5:
                dp.pursuit_kdj_die_stock_amount = '<span class="uk-badge uk-badge-danger">'+str(dp.pursuit_kdj_die_stock_amount)+'</span>'
            else:
                dp.pursuit_kdj_die_stock_amount = '<span class="uk-badge uk-badge-success">'+str(dp.pursuit_kdj_die_stock_amount)+'</span>'

            if dp.run_stock_ratio > 0.02484:
                dp.run_stock_amount = '<span class="uk-badge uk-badge-danger">'+str(dp.run_stock_amount)+'</span>'
            else:
                dp.run_stock_amount = '<span class="uk-badge uk-badge-success">'+str(dp.run_stock_amount)+'</span>'

            if dp.iron_stock_amount >= 2:
                dp.iron_stock_amount = '<span class="uk-badge uk-badge-danger">'+str(dp.iron_stock_amount)+'</span>'
            else:
                dp.iron_stock_amount = '<span class="uk-badge uk-badge-success">'+str(dp.iron_stock_amount)+'</span>'

            if dp.bank_stock_amount >= 2:
                dp.bank_stock_amount = '<span class="uk-badge uk-badge-danger">'+str(dp.bank_stock_amount)+'</span>'
            else:
                dp.bank_stock_amount = '<span class="uk-badge uk-badge-success">'+str(dp.bank_stock_amount)+'</span>'

            inc_str = str(round_float(dp.increase_range*100))+'%'
            if dp.increase_range >= 0.015:
                dp.increase_range = '<span class="uk-badge uk-badge-warning">'+inc_str+'</span>'
            elif dp.increase_range <= -0.015:
                dp.increase_range = '<span class="uk-badge uk-badge-danger">'+inc_str+'</span>'
            else:
                dp.increase_range = '<span class="uk-badge uk-badge-success">'+inc_str+'</span>'

    return {
        '__template__': 'param_records.html',
        'dps': dps
    }

@asyncio.coroutine
async def get_index_info(request, date):
    must_log_in(request)
    check_admin(request)
    if not date:
        date = today()
    shanghai_index = get_shanghai_index_info(date)
    if not shanghai_index:
        raise APIPermissionError()
    shanghai_index = round_float(shanghai_index)
    index_list = []
    daily_params = await DailyParam.findAll('date<=?', [date], orderBy='date desc', limit=4)
    increase_range = ''
    if len(daily_params) > 0:
        if daily_params[0].date == date and len(daily_params) >= 2:
            increase_range = (shanghai_index-daily_params[1].shanghai_index)/daily_params[1].shanghai_index
            increase_range = round_float(increase_range, 4)
        if daily_params[0].date != date and len(daily_params) >= 1:
            increase_range = (shanghai_index-daily_params[0].shanghai_index)/daily_params[0].shanghai_index
            increase_range = round_float(increase_range, 4)
        if daily_params[0].date == date and len(daily_params) >= 4:
            index_list = [shanghai_index, daily_params[1].shanghai_index, daily_params[2].shanghai_index, daily_params[3].shanghai_index]
        if daily_params[0].date != date and len(daily_params) >= 3:
            index_list = [shanghai_index, daily_params[0].shanghai_index, daily_params[1].shanghai_index, daily_params[2].shanghai_index]
    three_days_average_shanghai_increase = ''
    if len(index_list) == 4:
        sum = 0
        for i in range(0, 3):
            sum = sum + (index_list[i]-index_list[i+1])/index_list[i+1]
        three_days_average_shanghai_increase = round_float(sum/3, 4)
    return dict(shanghai_index=shanghai_index, increase_range=increase_range, three_days_average_shanghai_increase=three_days_average_shanghai_increase)