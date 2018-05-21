#!/usr/bin/env python3
# -*- coding: utf-8 -*-

__author__ = 'Chaoliang Zhong'

' url handlers '

import re, time, json, logging, hashlib, base64, asyncio, datetime, random

from datetime import timedelta
from aiohttp import web
from coroweb import get, post
from apis import APIValueError, APIResourceNotFoundError, APIError, APIPermissionError

from models import User, Account, AccountRecord, StockHoldRecord, StockTradeRecord, AccountAssetChange, DailyParam, ConditionProb, DailyConditionProb, DailyIndexE, StockSuccessDetail, next_id, today, convert_date, round_float, this_month, last_month
from config import configs
from stock_info import get_current_price, compute_fee, get_sell_price, get_stock_via_name, get_stock_via_code, get_shanghai_index_info, find_open_price_with_code
from handler_help import get_stock_method, get_profit_rate_by_month, get_profit_rate, get_shanghai_profit_rate_by_month, get_shenzhen_profit_rate_by_month, get_shenzhen_profit_rate, get_shanghai_profit_rate, less_or_close, greater_or_close, greater_not_close, less_not_close, add_account_update_date
from orm import get_pool
from operator import attrgetter

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
    all_accounts = await add_account_update_date(all_accounts)
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
@get('/stock_success_detail')
async def stock_success_detail(request):
    if not has_logged_in(request):
        return web.HTTPFound('/signin')
    return {
        '__template__': 'stock_success_detail.html',
        'amount': 0,
        'stock_success_details': []
    }

@asyncio.coroutine
@get('/stock_success_detail/{e1}/{e2}/{e3}/{e4}/{profit}/{turnover}/{increase}/{buy_or_follow}/{page}')
async def stock_success_detail_2(request, *, e1, e2, e3, e4, profit, turnover, increase, buy_or_follow, page):
    if not has_logged_in(request):
        return web.HTTPFound('/signin')
    try:
        e1 = int(e1)
        e2 = int(e2)
        e3 = int(e3)
        e4 = int(e4)
        buy_or_follow = int(buy_or_follow)
        page = int(page)
    except ValueError as e:
        raise APIPermissionError()
    stock_success_details = await StockSuccessDetail.findAll('e1=? and e2=? and e3=? and e4=? and winner=? and turnover=? and increase=? and buy_or_follow=?', [e1,e2,e3,e4,profit,turnover,increase,buy_or_follow], orderBy='date desc', limit=((page-1)*configs.stock.stock_detail_items_on_page, configs.stock.stock_detail_items_on_page))
    all_stock_success_details = await StockSuccessDetail.findAll('e1=? and e2=? and e3=? and e4=? and winner=? and turnover=? and increase=? and buy_or_follow=?', [e1,e2,e3,e4,profit,turnover,increase,buy_or_follow])
    return {
        '__template__': 'stock_success_detail.html',
        'amount': len(all_stock_success_details),
        'items_on_page': configs.stock.stock_detail_items_on_page,
        'stock_success_details': stock_success_details,
        'e1':e1,
        'e2':e2,
        'e3':e3,
        'e4':e4,
        'winner':profit,
        'turnover':turnover,
        'increase':increase,
        'buy_or_follow':buy_or_follow,
        'page': page
    }

@asyncio.coroutine
@get('/profit_rank')
async def profit_rank(request):
    if not has_logged_in(request):
        return web.HTTPFound('/signin')
    ranks = []
    data = {
        'legends': [],
        'x_data': [],
        'y_data': []
    }

    y, m = this_month().split('-')
    accounts = await Account.findAll('user_id=?', [request.__user__.id])

    account_ids = []
    account_id_strs = []
    for account in accounts:
        data['legends'].append(account.name)
        account_ids.append(account.id)
        account_id_strs.append('account_id=?')
    records = await AccountRecord.findAll(' or '.join(account_id_strs), account_ids, orderBy='date desc', limit=1)
    if len(records) > 0:
        y, m, d = records[0].date.split('-')

    data['legends'].append('上证综指')
    data['legends'].append('深证成指')

    y_values = {}

    while True:
        m_accounts = []
        for account in accounts:
            profit_rate = await get_profit_rate_by_month(account.id, y, m)
            if profit_rate:
                m_accounts.append(profit_rate)
                y_values['-'.join([account.name, y, m])] = profit_rate['profit_rate']
        if len(m_accounts) == 0:
            break
        data['x_data'].insert(0, '-'.join([y, m]))
        shanghai_profit_rate = await get_shanghai_profit_rate_by_month(y, m)
        if shanghai_profit_rate:
            m_accounts.append(shanghai_profit_rate)
            y_values['-'.join(['上证综指', y, m])] = shanghai_profit_rate['profit_rate']
        shenzhen_profit_rate = await get_shenzhen_profit_rate_by_month(y, m)
        if shenzhen_profit_rate:
            m_accounts.append(shenzhen_profit_rate)
            y_values['-'.join(['深证成指', y, m])] = shenzhen_profit_rate['profit_rate']
        m_accounts.sort(key=lambda x : x.get('profit_rate'), reverse=True)
        ranks.append({
            'year': y,
            'month': m,
            'accounts': m_accounts
        })
        y, m = last_month(y + '-' + m).split('-')

    for i in data['legends']:
        y_data = []
        for j in data['x_data']:
            if '-'.join([i, j]) in y_values.keys():
                y_data.append(y_values['-'.join([i, j])])
            else:
                y_data.append(0)
        data['y_data'].append(y_data)
    return {
        '__template__': 'profit_rank.html',
        'ranks': ranks,
        'data': data
    }

@asyncio.coroutine
@get('/profit_rank/{start_date}/{end_date}')
async def profit_rank_2(request, *, start_date, end_date):
    if not has_logged_in(request):
        return web.HTTPFound('/signin')

    accounts = await Account.findAll('user_id=?', [request.__user__.id])

    rank = []
    for account in accounts:
        profit_rate = await get_profit_rate(account.id, start_date, end_date)
        if profit_rate:
            rank.append(profit_rate)
    shanghai_profit_rate = await get_shanghai_profit_rate(start_date, end_date)
    if shanghai_profit_rate:
        rank.append(shanghai_profit_rate)
    shenzhen_profit_rate = await get_shenzhen_profit_rate(start_date, end_date)
    if shenzhen_profit_rate:
        rank.append(shenzhen_profit_rate)
    rank.sort(key=lambda x : x.get('profit_rate'), reverse=True)
    return {
        '__template__': 'profit_rank.html',
        'rank': rank,
        'start_date': start_date,
        'end_date': end_date
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
        all_accounts = await add_account_update_date(all_accounts)
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
    async with get_pool().get() as conn:
        await conn.begin()
        try:
            user = User(id=uid, name=name.strip(), email=email, passwd=hashlib.sha1(sha1_passwd.encode('utf-8')).hexdigest(), image='http://www.gravatar.com/avatar/%s?d=mm&s=120' % hashlib.md5(email.encode('utf-8')).hexdigest())
            await user.save(conn)
            await conn.commit()
            # make session cookie:
            r = web.Response()
            r.set_cookie(COOKIE_NAME, user2cookie(user, 86400), max_age=86400, httponly=True)
            user.passwd = '******'
            r.content_type = 'application/json'
            r.body = json.dumps(user, ensure_ascii=False).encode('utf-8')
        except BaseException as e:
            await conn.rollback()
            raise
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
    async with get_pool().get() as conn:
        await conn.begin()
        try:
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
                    await account_record.save(conn)
                    await conn.commit()

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
                            await new_stock.save(conn)
                        await conn.commit()
                        account_record.total_stock_value = total_stock_value
                        account_record.total_assets = round_float(account_record.security_funding + account_record.bank_funding + account_record.total_stock_value)
                        account_record.total_profit = round_float(account_record.total_assets - account_record.principle)
                        account_record.stock_position = round_float(account_record.total_stock_value * 100 / account_record.total_assets)
                        account_record.float_profit_lost = round_float(float_profit_lost)
                        await account_record.update(conn)
                        await conn.commit()
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
                        await stock.update(conn)
                    await conn.commit()
                    account_record.total_stock_value = total_stock_value
                    account_record.total_assets = round_float(account_record.security_funding + account_record.bank_funding + account_record.total_stock_value)
                    account_record.total_profit = round_float(account_record.total_assets - account_record.principle)
                    account_record.stock_position = round_float(account_record.total_stock_value * 100 / account_record.total_assets)
                    account_record.float_profit_lost = round_float(float_profit_lost)
                    await account_record.update(conn)
                    await conn.commit()
        except BaseException as e:
            await conn.rollback()
            raise
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
        return web.HTTPFound('/account/create')

    all_accounts = await add_account_update_date(all_accounts)

    account_records = await AccountRecord.findAll('account_id=?', [account.id], orderBy='date desc')
    most_recent_account_record = False

    clear = False
    max_position = 0
    dp = await DailyParam.findAll(orderBy='date desc', limit=1)
    can_buy_method_1 = True
    can_buy_method_2 = True
    if len(dp)>0:
        dadieweizhidie = False
        dp1 = await DailyParam.findAll('increase_range<?', [-0.015], orderBy='date desc', limit=1)
        if len(dp1)>0:
            dp2 = await DailyParam.findAll('date>? and increase_range>?', [dp1[0].date, 0], orderBy='date desc', limit=1)
            if len(dp2)==0:
                dadieweizhidie = True 
        # 最大仓位
        if dp[0].stock_market_status == 0:
            max_position = 0.25
            if not dp[0].big_fall_after_multi_bank_iron:
                max_position = 0.125
        if dp[0].stock_market_status == 1 or dp[0].stock_market_status == 2:
            max_position = 1
            if dadieweizhidie or not dp[0].big_fall_after_multi_bank_iron:
                max_position = 0.5

        clear = dp[0].shanghai_break_twenty_days_line_obviously or dp[0].shenzhen_break_twenty_days_line_obviously or dp[0].shanghai_break_twenty_days_line_for_two_days or dp[0].shenzhen_break_twenty_days_line_for_two_days or (dp[0].run_stock_ratio>0.02484 and dp[0].pursuit_stock_ratio<0.03)

        dp3 = await DailyParam.findAll('date<=?', [today()], orderBy='date desc', limit=5)
        pre_state = -1
        flag1 = False
        xiong_to_niu = False
        for d in dp3:
            if d.shanghai_break_twenty_days_line_obviously or d.shenzhen_break_twenty_days_line_obviously or d.shanghai_break_twenty_days_line_for_two_days or d.shenzhen_break_twenty_days_line_for_two_days or (d.run_stock_ratio>0.02484 and d.pursuit_stock_ratio<0.03):
                flag1 = True
            if (d.stock_market_status == 0) and (pre_state == 1 or pre_state == 2):
                xiong_to_niu = True
            pre_state = d.stock_market_status
        dp4 = await DailyParam.findAll('date<=?', [today()], orderBy='date desc', limit=2)
        flag2 = False
        for d in dp4:
            if d.pursuit_kdj_die_stock_ratio>=0.5:
                flag2 = True
                break

        flag3 = dp[0].shanghai_break_twenty_days_line or dp[0].shenzhen_break_twenty_days_line or dp[0].pursuit_stock_ratio<0.0036 or dp[0].strong_pursuit_stock_ratio<0.0018 or (dp[0].stock_market_status==0 and dp[0].method2_bigger_9_ratio>0.00155) or flag2
        flag4 = flag1 and not (xiong_to_niu and (dp[0].stock_market_status == 1 or dp[0].stock_market_status == 2))
        # 不能买
        cant_buy = dadieweizhidie or dp[0].four_days_pursuit_ratio_decrease or flag4 or flag3 or (dp[0].iron_stock_amount>1 or dp[0].bank_stock_amount>1)
        can_buy_method_1 = (not cant_buy) or ((dadieweizhidie or flag4) and not flag3)
        can_buy_method_2 = not cant_buy

        # 方式1买入仓位
        method1_buy_position = 1/4
        if not cant_buy:
            if not dp[0].big_fall_after_multi_bank_iron:
                method1_buy_position = method1_buy_position/2
        else:
            if can_buy_method_1 and dadieweizhidie:
                method1_buy_position = method1_buy_position/4
            elif can_buy_method_1:
                method1_buy_position = method1_buy_position/3
            else:
                method1_buy_position = 0

        # 方式2买入仓位
        method2_buy_position = 1/16
        if dp[0].stock_market_status == 0:
            if not can_buy_method_2:
                method2_buy_position = 0
            elif not dp[0].big_fall_after_multi_bank_iron:
                method2_buy_position = method2_buy_position/2
        if dp[0].stock_market_status == 1:
            method2_buy_position = 1/10
            if not can_buy_method_2:
                method2_buy_position = 0
        if dp[0].stock_market_status == 2:
            method2_buy_position = 1/6
            if not can_buy_method_2:
                method2_buy_position = 0

    advices = []
    current_position = 0
    if len(account_records)>0:
        # 当前仓位
        current_position = account_records[0].stock_position / 100
        most_recent_account_record = account_records[0]
        stocks = await StockHoldRecord.findAll('account_record_id=?', [most_recent_account_record.id])
    if clear:
        advices.append('<span style="color:red"><strong>今日务必择机清仓！</strong><small><br>勿急，收盘前清即可。</small></span>')
        if len(account_records)>0 and len(stocks)>0:
            for stock in stocks:
                stock_method = await get_stock_method(stock.stock_name, stock.stock_buy_date)
                if stock_method:
                    if stock_method == 1:
                        stock_method_str = '<span class="uk-badge">方式一</span>'
                    elif stock_method == 2:
                        stock_method_str = '<span class="uk-badge uk-badge-success">方式二</span>'
                    else:
                        stock_method_str = ''
                else:
                    stock_method_str = ''
                advices.append('收盘前以'+str(stock.stock_sell_price)+'元<span class="uk-badge uk-badge-danger">卖出</span>'+stock_method_str+stock.stock_name+str(stock.stock_amount)+'股')
    else:
        has_method_1 = False
        if len(account_records)>0:
            if current_position >= max_position:
                can_buy_method_2 = False
            if len(stocks) > 0:
                for stock in stocks:
                    d = convert_date(stock.stock_buy_date) + timedelta(days=configs.stock.max_stock_hold_days_method_2)
                    stock_method = await get_stock_method(stock.stock_name, stock.stock_buy_date)
                    if stock_method:
                        if stock_method == 1:
                            has_method_1 = True
                            stock_method_str = '<span class="uk-badge">方式一</span>'
                            d = convert_date(stock.stock_buy_date) + timedelta(days=configs.stock.max_stock_hold_days_method_1)
                        elif stock_method == 2:
                            stock_method_str = '<span class="uk-badge uk-badge-success">方式二</span>'
                            d = convert_date(stock.stock_buy_date) + timedelta(days=configs.stock.max_stock_hold_days_method_2)
                        else:
                            stock_method_str = ''
                    else:
                        stock_method_str = ''
                    if d < datetime.datetime.today():
                        advices.append('收盘前<span class="uk-badge uk-badge-danger">卖出</span>'+stock_method_str+stock.stock_name+str(stock.stock_amount)+'股')
                    else:
                        d_str = d.strftime("%Y-%m-%d")
                        advices.append(d_str+'前以'+str(stock.stock_sell_price)+'元<span class="uk-badge uk-badge-danger">卖出</span>'+stock_method_str+stock.stock_name+str(stock.stock_amount)+'股')
                advices[-1] = advices[-1] + '<br><span style="color:Orange"><strong>若股票持有期间有过停牌，则按停牌日顺延</strong></span>'
        bought = False
        if can_buy_method_1 and len(dp)>0 and dp[0].method_1:
            stocks = get_stock_via_name(dp[0].method_1)
            buy_position = max_position - current_position if method1_buy_position>max_position - current_position else method1_buy_position
            # 如果可买仓位已满，那么检查是否持有方式一的股票，如果已经持有，那么不能买，否则可以买
            if buy_position>0 or not has_method_1:
                buy_position = method1_buy_position
                if not stocks or len(stocks)!=1:
                    amount = int(round_float(buy_position*100))
                    if amount>0:
                        advices.append('以开盘价<span class="uk-badge uk-badge-success">买入</span><span class="uk-badge">方式一</span>'+dp[0].method_1+str(amount)+'%仓')
                        bought = True
                else:
                    stock_code = stocks[0]['stock_code']
                    price = find_open_price_with_code(stock_code)
                    if not price:
                        price = get_current_price(stock_code, today())
                    if price:
                        amount = int(round_float(most_recent_account_record.total_assets*buy_position/price/100, 0)*100)
                        if amount>0:
                            advices.append('以开盘价<span class="uk-badge uk-badge-success">买入</span><span class="uk-badge">方式一</span>'+dp[0].method_1+str(amount)+'股')
                            bought = True
                    else:
                        advices.append('以开盘价<span class="uk-badge uk-badge-success">买入</span><span class="uk-badge">方式一</span>'+dp[0].method_1+str(round_float(buy_position*100))+'%仓')
                        bought = True
        elif can_buy_method_2 and len(dp)>0 and dp[0].method_2:
            stocks = get_stock_via_name(dp[0].method_2)
            buy_position = max_position - current_position if method2_buy_position>max_position - current_position else method2_buy_position
            if buy_position>0:
                if not stocks or len(stocks)!=1:
                    amount = int(round_float(buy_position*100))
                    if amount>0:
                        advices.append('以开盘价<span class="uk-badge uk-badge-success">买入</span><span class="uk-badge uk-badge-success">方式二</span>'+dp[0].method_2+str(amount)+'%仓')
                        bought = True
                else:
                    stock_code = stocks[0]['stock_code']
                    price = find_open_price_with_code(stock_code)
                    if not price:
                        price = get_current_price(stock_code, today())
                    if price:
                        amount = int(round_float(most_recent_account_record.total_assets*buy_position/price/100, 0)*100)
                        if amount>0:
                            advices.append('以开盘价<span class="uk-badge uk-badge-success">买入</span><span class="uk-badge uk-badge-success">方式二</span>'+dp[0].method_2+str(amount)+'股')
                            bought = True
                    else:
                        advices.append('以开盘价<span class="uk-badge uk-badge-success">买入</span><span class="uk-badge uk-badge-success">方式二</span>'+dp[0].method_2+str(round_float(buy_position*100))+'%仓')
                        bought = True
        if not bought:
            advices.append('<span style="color:red"><strong>今日不能买入股票！</strong></span>')
    if account.success_times + account.fail_times==0:
        account.success_ratio = 0
    else:
        account.success_ratio = str(account.success_times) + '/(' + str(account.success_times) + '+' + str(account.fail_times) + ')=' + str(round_float(account.success_times*100/(account.success_times + account.fail_times)))

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
        'exit_right_action': '/api/exit_right',
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
                for record in stock_hold_records:
                    record.stop_loss_price = round_float(record.stock_sell_price / 1.034 * 0.905)
                account_record.stock_hold_records = stock_hold_records
                if len(stock_hold_records)>max_amount:
                    max_amount = len(stock_hold_records)
            else:
                account_record.stock_hold_records = []
        for account_record in account_records:
            for x in range(max_amount-len(account_record.stock_hold_records)):
                account_record.stock_hold_records.append({'stock_name':'-', 'stock_amount':0, 'stock_current_price':0, 'stock_sell_price':0, 'stop_loss_price':0})
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
            async with get_pool().get() as conn:
                await conn.begin()
                try:
                    for stock in stock_hold_records:
                        # TODO 改成从数据库读取
                        current_price = get_current_price(stock.stock_code, date)
                        if current_price:
                            stock.stock_current_price = current_price
                            await stock.update(conn)
                            price_update = True
                        float_profit_lost = float_profit_lost + (stock.stock_current_price-stock.stock_buy_price)*stock.stock_amount - compute_fee(True, account.commission_rate, stock.stock_code, stock.stock_buy_price, stock.stock_amount)
                        total_stock_value = total_stock_value + stock.stock_current_price*stock.stock_amount
                        stock.stop_loss_price = round_float(stock.stock_sell_price / 1.034 * 0.905)
                    if price_update:
                        account_record.float_profit_lost = round_float(float_profit_lost)
                        account_record.total_stock_value = round_float(total_stock_value)
                        account_record.total_assets = round_float(account_record.total_stock_value + account_record.security_funding + account_record.bank_funding)
                        account_record.total_profit = round_float(account_record.total_assets - account_record.principle)
                        account_record.stock_position = round_float(account_record.total_stock_value * 100 / account_record.total_assets)
                        rows = await account_record.update(conn)
                    account_record.stock_hold_records = stock_hold_records
                    await conn.commit()
                except BaseException as e:
                    await conn.rollback()
                    raise APIPermissionError()
        else:
            account_record.stock_hold_records = []
        for x in range(stock_amount-len(account_record.stock_hold_records)):
            account_record.stock_hold_records.append({'stock_name':'-', 'stock_amount':0, 'stock_current_price':0, 'stock_sell_price':0, 'stop_loss_price':0})
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
async def api_modify_account(request, *, id, name, buy_strategy, sell_strategy, commission_rate):
    must_log_in(request)
    account = await Account.find(id)
    if not account:
        raise APIValueError('name', '账户不存在')
    if account.user_id != request.__user__.id:
        raise APIValueError('name', '没有操作该账户的权限')
    if not name or not name.strip():
        raise APIValueError('name', '账户名称不能为空')
    if not buy_strategy or not buy_strategy.strip():
        raise APIValueError('buy_strategy', '买入策略不能为空')
    if not sell_strategy or not sell_strategy.strip():
        raise APIValueError('sell_strategy', '卖出策略不能为空')
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
    account.buy_strategy = buy_strategy.strip()
    account.sell_strategy = sell_strategy.strip()
    account.commission_rate = commission_rate
    async with get_pool().get() as conn:
        await conn.begin()
        try:
            await account.update(conn)
            await conn.commit()
        except BaseException as e:
            await conn.rollback()
            raise APIValueError('name', '修改账户失败')
    return account

@asyncio.coroutine
@post('/api/accounts')
async def api_create_account(request, *, name, buy_strategy, sell_strategy, commission_rate, initial_funding, date):
    must_log_in(request)
    if not name or not name.strip():
        raise APIValueError('name', '账户名称不能为空')
    accounts = await Account.findAll('name=? and user_id=?', [name.strip(), request.__user__.id])
    if len(accounts) > 0:
        raise APIValueError('name', '账户名称已被用')
    if not buy_strategy or not buy_strategy.strip():
        raise APIValueError('buy_strategy', '买入策略不能为空')
    if not sell_strategy or not sell_strategy.strip():
        raise APIValueError('sell_strategy', '卖出策略不能为空')
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
    async with get_pool().get() as conn:
        await conn.begin()
        try:
            account = Account(user_id=request.__user__.id, name=name.strip(), buy_strategy=buy_strategy.strip(), sell_strategy=sell_strategy.strip(), commission_rate=commission_rate, initial_funding=initial_funding)
            await account.save(conn)
            account_record = AccountRecord(date=date, account_id=account.id, stock_position=0, security_funding=0, bank_funding=round_float(initial_funding), total_stock_value=0, total_assets=round_float(initial_funding), float_profit_lost=0, total_profit=0, principle=round_float(initial_funding))
            await account_record.save(conn)
            await conn.commit()
        except BaseException as e:
            await conn.rollback()
            raise APIValueError('name', '创建账户失败')
    return account

@asyncio.coroutine
@post('/api/advanced/accounts')
async def api_advanced_create_account(request, *, name, buy_strategy, sell_strategy, commission_rate, initial_funding, initial_bank_funding, initial_security_funding, date):
    must_log_in(request)
    if not name or not name.strip():
        raise APIValueError('name', '账户名称不能为空')
    accounts = await Account.findAll('name=? and user_id=?', [name.strip(), request.__user__.id])
    if len(accounts) > 0:
        raise APIValueError('name', '账户名称已被用')
    if not buy_strategy or not buy_strategy.strip():
        raise APIValueError('buy_strategy', '买入策略不能为空')
    if not sell_strategy or not sell_strategy.strip():
        raise APIValueError('sell_strategy', '卖出策略不能为空')
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
    async with get_pool().get() as conn:
        await conn.begin()
        try:
            account = Account(user_id=request.__user__.id, name=name.strip(), buy_strategy=buy_strategy.strip(), sell_strategy=sell_strategy.strip(), commission_rate=commission_rate, initial_funding=initial_funding)
            await account.save(conn)
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
            await account_record.save(conn)
            await conn.commit()
        except BaseException as e:
            await conn.rollback()
            raise APIValueError('name', '创建账户失败')
    return account

@asyncio.coroutine
@post('/api/remove/accounts')
async def api_remove_account(request, *, account_id):
    must_log_in(request)
    if not account_id or not account_id.strip():
        return '删除账户失败(1)'
    account = await Account.find(account_id)
    if not account:
        return '删除账户失败(2)'
    if (not request.__user__.admin and request.__user__.id != account.user_id):
        return '删除账户失败(3)'

    async with get_pool().get() as conn:
        await conn.begin()
        try:
            await AccountAssetChange.removeAll(conn, 'account_id=?', [account.id])
            await StockTradeRecord.removeAll(conn, 'account_id=?', [account.id])
            account_records = await AccountRecord.findAll('account_id=?', [account.id])
            for account_record in account_records:
                await StockHoldRecord.removeAll(conn, 'account_record_id=?', [account_record.id])
            await AccountRecord.removeAll(conn, 'account_id=?', [account.id])
            await account.remove(conn)
            await conn.commit()
        except BaseException as e:
            await conn.rollback()
            return '删除账户失败(4)'
    return '删除账户成功'

@asyncio.coroutine
@post('/api/remove/account_records')
async def api_remove_account_record(request, *, account_record_id):
    must_log_in(request)
    if not account_record_id or not account_record_id.strip():
        return '删除账户记录失败(1)'
    account_record = await AccountRecord.find(account_record_id)
    if not account_record:
        return '删除账户记录失败(2)'
    account = await Account.find(account_record.account_id)
    if not account:
        return '删除账户记录失败(3)'
    if (not request.__user__.admin and request.__user__.id != account.user_id):
        return '删除账户记录失败(4)'
    all_account_records = await AccountRecord.findAll('account_id=?', [account.id])
    if len(all_account_records) == 1:
        return '仅有一条记录，不许删除'

    async with get_pool().get() as conn:
        await conn.begin()
        try:
            await StockTradeRecord.removeAll(conn, 'account_id=? and stock_date=?', [account.id, account_record.date])
            await AccountAssetChange.removeAll(conn, 'account_id=? and date=?', [account.id, account_record.date])
            await StockHoldRecord.removeAll(conn, 'account_record_id=?', [account_record_id])
            await account_record.remove(conn)
            await conn.commit()
        except BaseException as e:
            await conn.rollback()
            return '删除账户记录失败(5)'
    return '删除账户记录成功'

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

    try:
        account_record = await find_account_record(account_id, date)
    except BaseException as e:
        raise APIPermissionError()

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
    async with get_pool().get() as conn:
        await conn.begin()
        try:
            if len(exist_stocks) > 0:
                exist_stocks[0].stock_buy_price = (exist_stocks[0].stock_buy_price*exist_stocks[0].stock_amount + stock_price*stock_amount)/(exist_stocks[0].stock_amount + stock_amount)
                exist_stocks[0].stock_amount = exist_stocks[0].stock_amount + stock_amount
                exist_stocks[0].stock_sell_price = sell_price
                exist_stocks[0].stock_current_price=current_price
                await exist_stocks[0].update(conn)
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
                await new_stock.save(conn)

            await conn.commit()

            float_profit_lost = 0
            stocks = await StockHoldRecord.findAll('account_record_id=?', [account_record.id])
            for stock in stocks:
                float_profit_lost = float_profit_lost + (stock.stock_current_price-stock.stock_buy_price)*stock.stock_amount - compute_fee(True, accounts[0].commission_rate, stock.stock_code, stock.stock_buy_price, stock.stock_amount)
            
            account_record.float_profit_lost = round_float(float_profit_lost)

            await account_record.update(conn)

            stock_trade = StockTradeRecord(
                account_id=accounts[0].id,
                stock_code=stock_code,
                stock_name=stock_name,
                stock_amount=stock_amount,
                stock_price=stock_price,
                stock_operation=True,
                trade_series='0',
                stock_date=date)
            await stock_trade.save(conn)
            await conn.commit()
        except BaseException as e:
            await conn.rollback()
            raise APIValueError('stock_name', '买入失败')
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
    try:
        account_record = await find_account_record(account_id, date)
    except BaseException as e:
        raise APIPermissionError()
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

    async with get_pool().get() as conn:
        await conn.begin()
        try:
            stock_trade = StockTradeRecord(
                account_id=accounts[0].id,
                stock_code=stock_code,
                stock_name=stock_name,
                stock_amount=stock_amount,
                stock_price=stock_price,
                stock_operation=False,
                trade_series='0',
                stock_date=date)
            rows = 0
            rows = await stock_trade.save(conn)
            if rows != 1:
                raise APIValueError('stock_name', '卖出失败')
            await conn.commit()

            rows = 0
            if stock_amount == exist_stocks[0].stock_amount:
                buy_date = exist_stocks[0].stock_buy_date
                trade_series = exist_stocks[0].id
                rows = await exist_stocks[0].remove(conn)
                if rows != 1:
                    raise APIValueError('stock_name', '卖出失败')
                await conn.commit()
                stock_trades = await StockTradeRecord.findAll('account_id=? and stock_code=? and stock_date>=? and trade_series=?', [accounts[0].id, stock_code, buy_date, '0'])
                profit = 0
                for trade in stock_trades:
                    if trade.stock_operation:
                        profit = profit - trade.stock_amount*trade.stock_price - compute_fee(True, accounts[0].commission_rate, trade.stock_code, trade.stock_price, trade.stock_amount)
                    else:
                        profit = profit + trade.stock_amount*trade.stock_price - compute_fee(False, accounts[0].commission_rate, trade.stock_code, trade.stock_price, trade.stock_amount)
                    trade.trade_series = trade_series
                    await trade.update(conn)
                    await conn.commit()
                if profit>0:
                    accounts[0].success_times = accounts[0].success_times + 1;
                else:
                    accounts[0].fail_times = accounts[0].fail_times + 1;
                await accounts[0].update(conn)
                await conn.commit()
            else:
                exist_stocks[0].stock_amount = exist_stocks[0].stock_amount - stock_amount
                rows = await exist_stocks[0].update(conn)
                if rows != 1:
                    raise APIValueError('stock_name', '卖出失败')
                await conn.commit()
            if (rows == 1):
                float_profit_lost = 0
                stocks = await StockHoldRecord.findAll('account_record_id=?', [account_record.id])
                for stock in stocks:
                    float_profit_lost = float_profit_lost + (stock.stock_current_price-stock.stock_buy_price)*stock.stock_amount - compute_fee(True, accounts[0].commission_rate, stock.stock_code, stock.stock_buy_price, stock.stock_amount)
                account_record.float_profit_lost = round_float(float_profit_lost)
                rows = 0
                rows = await account_record.update(conn)
                if (rows == 1):
                    await conn.commit()
                else:
                    raise APIValueError('stock_name', '卖出失败')
        except BaseException as e:
            await conn.rollback()
            raise APIValueError('stock_name', '卖出失败')

    return accounts[0]


@asyncio.coroutine
@post('/api/exit_right')
async def api_exit_right(request, *, stock_name, stock_code, stock_amount, date, account_id):
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
        stock_amount = int(stock_amount)
    except ValueError as e:
        raise APIValueError('stock_amount', '股票数量填写不正确')
    if stock_amount <=  0:
        raise APIValueError('stock_amount', '股票数量必须大于0')
#    if stock_amount % 100 != 0:
#        raise APIValueError('stock_amount', '股票数量必须为100的整数')
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

    most_recent_account_record = await AccountRecord.findAll('account_id=?', [account_id], orderBy='date desc', limit=1)
    if len(most_recent_account_record) <= 0:
        raise APIValueError('date', '尚未持有任何股票')
    if date < most_recent_account_record[0].date:
        raise APIValueError('date', '日期不能早于最近持股日期')

    try:
        account_record = await find_account_record(account_id, date)
    except BaseException as e:
        raise APIPermissionError()
    exist_stocks = await StockHoldRecord.findAll('account_record_id=? and stock_code=?', [account_record.id, stock_code])
    if len(exist_stocks) <= 0:
        raise APIValueError('stock_amount', '未持有该股票')
    if exist_stocks[0].stock_amount >= stock_amount:
        raise APIValueError('stock_amount', '除权后股票数量应大于当前持有数量')

    async with get_pool().get() as conn:
        await conn.begin()
        try:
            rows = 0
            exist_stocks[0].stock_amount = stock_amount
            rows = await exist_stocks[0].update(conn)
            if rows != 1:
                raise APIValueError('stock_name', '除权失败')
            await conn.commit()
            account_record = await find_account_record(account_id, date)
        except BaseException as e:
            await conn.rollback()
            raise APIValueError('stock_name', '除权失败')
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

    try:
        account_record = await find_account_record(account_id, date.strip())
    except BaseException as e:
        raise APIPermissionError()

    if account_record.bank_funding < funding_amount:
        raise APIValueError('funding_amount', '转账金额不足')

    async with get_pool().get() as conn:
        await conn.begin()
        try:
            account_record.bank_funding = round_float(account_record.bank_funding - funding_amount)
            account_record.security_funding = round_float(account_record.security_funding + funding_amount)
            await account_record.update(conn)

            security_funding_change = AccountAssetChange(
                account_id=account_id,
                change_amount=funding_amount,
                operation=1,
                security_or_bank=True,
                date=date)

            await security_funding_change.save(conn)

            bank_funding_change = AccountAssetChange(
                account_id=account_id,
                change_amount=funding_amount,
                operation=0,
                security_or_bank=False,
                date=date)

            await bank_funding_change.save(conn)
            await conn.commit()
        except BaseException as e:
            await conn.rollback()
            raise APIValueError('funding_amount', '银证转账失败')

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

    try:
        account_record = await find_account_record(account_id, date.strip())
    except BaseException as e:
        raise APIPermissionError()

    if account_record.security_funding < funding_amount:
        raise APIValueError('funding_amount', '转账金额不足')

    async with get_pool().get() as conn:
        await conn.begin()
        try:
            account_record.bank_funding = round_float(account_record.bank_funding + funding_amount)
            account_record.security_funding = round_float(account_record.security_funding - funding_amount)
            await account_record.update(conn)

            security_funding_change = AccountAssetChange(
                account_id=account_id,
                change_amount=funding_amount,
                operation=0,
                security_or_bank=True,
                date=date)

            await security_funding_change.save(conn)

            bank_funding_change = AccountAssetChange(
                account_id=account_id,
                change_amount=funding_amount,
                operation=1,
                security_or_bank=False,
                date=date)

            await bank_funding_change.save(conn)
            await conn.commit()
        except BaseException as e:
            await conn.rollback()
            raise APIValueError('funding_amount', '银证转账失败')

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

    try:
        account_record = await find_account_record(account_id, date.strip())
    except BaseException as e:
        raise APIPermissionError()

    async with get_pool().get() as conn:
        await conn.begin()
        try:
            account_record.bank_funding = round_float(account_record.bank_funding + funding_amount)
            account_record.principle = round_float(account_record.principle + funding_amount)
            account_record.total_assets = round_float(account_record.total_assets + funding_amount)
            if account_record.total_assets > 0:
                account_record.stock_position = round_float(account_record.total_stock_value * 100 / account_record.total_assets)
            else:
                account_record.stock_position = 0
            await account_record.update(conn)

            bank_funding_change = AccountAssetChange(
                account_id=account_id,
                change_amount=funding_amount,
                operation=1,
                security_or_bank=False,
                date=date)

            await bank_funding_change.save(conn)
            await conn.commit()
        except BaseException as e:
            await conn.rollback()
            raise APIValueError('funding_amount', '增加金额失败')

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

    try:
        account_record = await find_account_record(account_id, date.strip())
    except BaseException as e:
        raise APIPermissionError()

    if (account_record.bank_funding < funding_amount):
        raise APIValueError('funding_amount', '金额不足')

    async with get_pool().get() as conn:
        await conn.begin()
        try:
            account_record.bank_funding = round_float(account_record.bank_funding - funding_amount)
            account_record.principle = round_float(account_record.principle - funding_amount)
            account_record.total_assets = round_float(account_record.total_assets - funding_amount)
            if account_record.total_assets > 0:
                account_record.stock_position = round_float(account_record.total_stock_value * 100 / account_record.total_assets)
            else:
                account_record.stock_position = 0
            await account_record.update(conn)

            bank_funding_change = AccountAssetChange(
                account_id=account_id,
                change_amount=funding_amount,
                operation=0,
                security_or_bank=False,
                date=date)

            await bank_funding_change.save(conn)
            await conn.commit()
        except BaseException as e:
            await conn.rollback()
            raise APIValueError('funding_amount', '减少金额失败')

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

    try:
        account_record = await find_account_record(account_id, date.strip())
    except BaseException as e:
        raise APIPermissionError()

    account_record.security_funding = funding_amount

    account_record.total_assets = round_float(account_record.total_stock_value + account_record.bank_funding + account_record.security_funding)
    if account_record.total_assets >0:
        account_record.stock_position = round_float(account_record.total_stock_value * 100 / account_record.total_assets)
    else:
        account_record.stock_position = 0
    account_record.total_profit = round_float(account_record.total_assets - account_record.principle)

    async with get_pool().get() as conn:
        await conn.begin()
        try:
            await account_record.update(conn)

            security_funding_change = AccountAssetChange(
                account_id=account_id,
                change_amount=funding_amount,
                operation=2,
                security_or_bank=True,
                date=date)

            await security_funding_change.save(conn)
            await conn.commit()
        except BaseException as e:
            await conn.rollback()
            raise APIValueError('funding_amount', '修改金额失败')

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
@get('/up_to_date_all')
async def api_up_to_date_all(request):
    must_log_in(request)
    accounts = await Account.findAll('user_id=?', [request.__user__.id])
    if len(accounts) <=0:
        raise APIPermissionError()

    for account in accounts:
        account_record = await find_account_record(account.id, today())

    return web.HTTPFound('/account')

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
    all_accounts = await add_account_update_date(all_accounts)
    dp = await DailyParam.find(date)
    di = await DailyIndexE.find(date)
    if di is None:
        di = DailyIndexE(
            date = date,
            e1 = 0,
            e2 = 0,
            e3 = 0,
            e4 = 0
        )

    if dp:
        dp.twenty_days_line = int(dp.twenty_days_line)
        dp.shanghai_break_twenty_days_line = int(dp.shanghai_break_twenty_days_line)
        dp.shanghai_break_twenty_days_line_obviously = int(dp.shanghai_break_twenty_days_line_obviously)
        dp.shanghai_break_twenty_days_line_for_two_days = int(dp.shanghai_break_twenty_days_line_for_two_days)
        dp.shenzhen_break_twenty_days_line = int(dp.shenzhen_break_twenty_days_line)
        dp.shenzhen_break_twenty_days_line_obviously = int(dp.shenzhen_break_twenty_days_line_obviously)
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
        dp.method2_bigger_9_amount = ''
        dp.method_1 = ''
        dp.method_2 = ''
        dps = await DailyParam.findAll(orderBy='date desc', limit=1)
        futures = ''
        if len(dps)>0:
            dp.futures = dps[0].futures
            dp.stock_market_status = dps[0].stock_market_status
            dp.twenty_days_line = int(dps[0].twenty_days_line)
            dp.shanghai_break_twenty_days_line = int(dps[0].shanghai_break_twenty_days_line)
            dp.shanghai_break_twenty_days_line_obviously = int(dps[0].shanghai_break_twenty_days_line_obviously)
            dp.shanghai_break_twenty_days_line_for_two_days = int(dps[0].shanghai_break_twenty_days_line_for_two_days)
            dp.shenzhen_break_twenty_days_line = int(dps[0].shenzhen_break_twenty_days_line)
            dp.shenzhen_break_twenty_days_line_obviously = int(dps[0].shenzhen_break_twenty_days_line_obviously)
            dp.shenzhen_break_twenty_days_line_for_two_days = int(dps[0].shenzhen_break_twenty_days_line_for_two_days)
        else:
            dp.futures = ''
            dp.stock_market_status = 0
            dp.twenty_days_line = 0
            dp.shanghai_break_twenty_days_line = 0
            dp.shanghai_break_twenty_days_line_obviously = 0
            dp.shanghai_break_twenty_days_line_for_two_days = 0
            dp.shenzhen_break_twenty_days_line = 0
            dp.shenzhen_break_twenty_days_line_obviously = 0
            dp.shenzhen_break_twenty_days_line_for_two_days = 0
    return {
        '__template__': 'param_statistical.html',
        'dp': dp,
        'di': di,
        'accounts': all_accounts,
        'action': '/api/param_statistical'
    }

@asyncio.coroutine
@post('/api/param_statistical')
async def api_param_statistical(request, *, date, shanghai_index, stock_market_status, twenty_days_line, sz_twenty_days_line, sh_sz_upper, sh_sz_bigger, increase_range, 
                                three_days_average_shanghai_increase, shanghai_break_twenty_days_line, shanghai_break_twenty_days_line_obviously, 
                                shanghai_break_twenty_days_line_for_two_days, shenzhen_break_twenty_days_line, shenzhen_break_twenty_days_line_obviously,
                                shenzhen_break_twenty_days_line_for_two_days, all_stock_amount, buy_stock_amount, pursuit_stock_amount,
                                iron_stock_amount, bank_stock_amount, strong_pursuit_stock_amount, pursuit_kdj_die_stock_amount, run_stock_amount, method2_bigger_9_amount,
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

    try:
        shanghai_index = float(shanghai_index)
    except ValueError as e:
        raise APIValueError('shanghai_index', '沪指指数填写不正确')
    if shanghai_index <= 0:
        raise APIValueError('shanghai_index', '沪指指数必须大于0')

    try:
        three_days_average_shanghai_increase = float(three_days_average_shanghai_increase)
    except ValueError as e:
        raise APIValueError('three_days_average_shanghai_increase', '沪指三天平均涨幅填写不正确')

    try:
        increase_range = float(increase_range)
    except ValueError as e:
        raise APIValueError('increase_range', '沪指涨幅填写不正确')

    try:
        all_stock_amount = int(all_stock_amount)
    except ValueError as e:
        raise APIValueError('all_stock_amount', '总股票数填写不正确')
    if all_stock_amount<=0:
        raise APIValueError('all_stock_amount', '总股票数填写不正确')

    try:
        buy_stock_amount = int(buy_stock_amount)
    except ValueError as e:
        raise APIValueError('buy_stock_amount', '发出买入信号的股票数填写不正确')
    if buy_stock_amount<0:
        raise APIValueError('buy_stock_amount', '发出买入信号的股票数填写不正确')

    try:
        pursuit_stock_amount = int(pursuit_stock_amount)
    except ValueError as e:
        raise APIValueError('pursuit_stock_amount', '发出追涨信号的股票数填写不正确')
    if pursuit_stock_amount<0:
        raise APIValueError('pursuit_stock_amount', '发出追涨信号的股票数填写不正确')
    pursuit_stock_ratio=pursuit_stock_amount/all_stock_amount

    try:
        iron_stock_amount = int(iron_stock_amount)
    except ValueError as e:
        raise APIValueError('iron_stock_amount', '发出买入或追涨信号的普钢股票数填写不正确')
    if iron_stock_amount<0:
        raise APIValueError('iron_stock_amount', '发出买入或追涨信号的普钢股票数填写不正确')

    try:
        bank_stock_amount = int(bank_stock_amount)
    except ValueError as e:
        raise APIValueError('bank_stock_amount', '发出买入或追涨信号的银行股票数填写不正确')
    if bank_stock_amount<0:
        raise APIValueError('bank_stock_amount', '发出买入或追涨信号的银行股票数填写不正确')

    try:
        strong_pursuit_stock_amount = int(strong_pursuit_stock_amount)
    except ValueError as e:
        raise APIValueError('strong_pursuit_stock_amount', '发出强烈追涨信号的股票数填写不正确')
    if strong_pursuit_stock_amount<0:
        raise APIValueError('strong_pursuit_stock_amount', '发出强烈追涨信号的股票数填写不正确')

    try:
        pursuit_kdj_die_stock_amount = int(pursuit_kdj_die_stock_amount)
    except ValueError as e:
        raise APIValueError('pursuit_kdj_die_stock_amount', '发出追涨信号但KDJ死叉的股票数填写不正确')
    if pursuit_kdj_die_stock_amount<0:
        raise APIValueError('pursuit_kdj_die_stock_amount', '发出追涨信号但KDJ死叉的股票数填写不正确')

    try:
        run_stock_amount = int(run_stock_amount)
    except ValueError as e:
        raise APIValueError('run_stock_amount', '发出逃顶信号的股票数填写不正确')
    if run_stock_amount<0:
        raise APIValueError('run_stock_amount', '发出逃顶信号的股票数填写不正确')

    try:
        method2_bigger_9_amount = int(method2_bigger_9_amount)
    except ValueError as e:
        raise APIValueError('method2_bigger_9_amount', '方式二涨幅大于9%股票数填写不正确')
    if method2_bigger_9_amount<0:
        raise APIValueError('method2_bigger_9_amount', '方式二涨幅大于9%股票数填写不正确')

    pursuit_kdj_die_stock_ratio = pursuit_kdj_die_stock_amount/pursuit_stock_amount if pursuit_stock_amount!=0 else 0

    big_fall_after_multi_bank_iron = True
    if increase_range <= -0.015:
        big_fall_after_multi_bank_iron = True
    elif iron_stock_amount>1 or bank_stock_amount>1:
        big_fall_after_multi_bank_iron = False
    else:
        dps1 = await DailyParam.findAll('(iron_stock_amount>? or bank_stock_amount>?) and date<=?', [1, 1, date], orderBy='date desc', limit=1)
        if len(dps1)>0:
            dps2 = await DailyParam.findAll('date>? and date<=? and increase_range<=?', [dps1[0].date, date, -0.015])
            if len(dps2) == 0:
                big_fall_after_multi_bank_iron = False
            else:
                big_fall_after_multi_bank_iron = True
        else:
            big_fall_after_multi_bank_iron = True

    four_days_pursuit_ratio_decrease = False
    dps3 = await DailyParam.findAll('date<?', [date], orderBy='date desc', limit=2)
    if len(dps3) == 2:
        if dps3[1].pursuit_stock_ratio >= 0.032 and dps3[0].pursuit_stock_ratio >= 0.032 and pursuit_stock_ratio<0.032:
            four_days_pursuit_ratio_decrease = True

    dp = await DailyParam.find(date)
    di = await DailyIndexE.find(date)
    async with get_pool().get() as conn:
        await conn.begin()
        try:
            e1 = twenty_days_line
            e2 = sz_twenty_days_line
            e3 = sh_sz_upper
            e4 = sh_sz_bigger
            if di:
                di.e1, di.e2, di.e3, di.e4 = e1, e2, e3, e4
                await di.update(conn)
            else:
                di = DailyIndexE(
                    date = date,
                    e1 = e1,
                    e2 = e2,
                    e3 = e3,
                    e4 = e4
                )
                await di.save(conn)
            if dp:
                dp.date = date
                dp.shanghai_index=shanghai_index
                dp.stock_market_status=int(stock_market_status)
                dp.twenty_days_line=True if str(twenty_days_line)=='1' else False
                dp.increase_range=increase_range
                dp.three_days_average_shanghai_increase=three_days_average_shanghai_increase
                dp.shanghai_break_twenty_days_line=True if str(shanghai_break_twenty_days_line)=='1' else False
                dp.shanghai_break_twenty_days_line_obviously=True if str(shanghai_break_twenty_days_line_obviously)=='1' else False
                dp.shanghai_break_twenty_days_line_for_two_days=True if str(shanghai_break_twenty_days_line_for_two_days)=='1' else False
                dp.shenzhen_break_twenty_days_line=True if str(shenzhen_break_twenty_days_line)=='1' else False
                dp.shenzhen_break_twenty_days_line_obviously=True if str(shenzhen_break_twenty_days_line_obviously)=='1' else False
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
                dp.method2_bigger_9_amount=method2_bigger_9_amount
                dp.method2_bigger_9_ratio=method2_bigger_9_amount/all_stock_amount
                dp.big_fall_after_multi_bank_iron=big_fall_after_multi_bank_iron
                dp.four_days_pursuit_ratio_decrease=four_days_pursuit_ratio_decrease
                dp.too_big_increase=(pursuit_stock_ratio>=0.03)
                dp.futures=futures
                dp.method_1=method_1
                dp.method_2=method_2
                await dp.update(conn)
            else:
                dp = DailyParam(date=date,
                                shanghai_index=shanghai_index,
                                stock_market_status=int(stock_market_status),
                                twenty_days_line=True if str(twenty_days_line)=='1' else False,
                                increase_range=increase_range,
                                three_days_average_shanghai_increase=three_days_average_shanghai_increase,
                                shanghai_break_twenty_days_line=True if str(shanghai_break_twenty_days_line)=='1' else False,
                                shanghai_break_twenty_days_line_obviously=True if str(shanghai_break_twenty_days_line_obviously)=='1' else False,
                                shanghai_break_twenty_days_line_for_two_days=True if str(shanghai_break_twenty_days_line_for_two_days)=='1' else False,
                                shenzhen_break_twenty_days_line=True if str(shenzhen_break_twenty_days_line)=='1' else False,
                                shenzhen_break_twenty_days_line_obviously=True if str(shenzhen_break_twenty_days_line_obviously)=='1' else False,
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
                                method2_bigger_9_amount=method2_bigger_9_amount,
                                method2_bigger_9_ratio=method2_bigger_9_amount/all_stock_amount,
                                big_fall_after_multi_bank_iron=big_fall_after_multi_bank_iron,
                                four_days_pursuit_ratio_decrease=four_days_pursuit_ratio_decrease,
                                too_big_increase=(pursuit_stock_ratio>=0.03),
                                futures=futures,
                                method_1=method_1,
                                method_2=method_2,
                                recommendation='')
                await dp.save(conn)
            await conn.commit()
            r = await get_recommend(dp)
            dp.recommendation = r
            await dp.update(conn)
            await conn.commit()
        except BaseException as e:
            await conn.rollback()
            raise APIValueError('date', '操作失败')
    return dp

@asyncio.coroutine
@get('/params')
async def do_params(request):
    if not has_logged_in(request):
        return web.HTTPFound('/signin')
    check_admin(request)
    all_accounts = await Account.findAll('user_id=?', [request.__user__.id])
    all_accounts = await add_account_update_date(all_accounts)
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

            if dp.method2_bigger_9_ratio > 0.00155:
                dp.method2_bigger_9_amount = '<span class="uk-badge uk-badge-danger">'+str(dp.method2_bigger_9_amount)+'</span>'
            else:
                dp.method2_bigger_9_amount = '<span class="uk-badge uk-badge-success">'+str(dp.method2_bigger_9_amount)+'</span>'

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
@get('/condition_prob')
async def do_condition_prob(request):
    if not has_logged_in(request):
        return web.HTTPFound('/signin')
    check_admin(request)
    all_accounts = await Account.findAll('user_id=?', [request.__user__.id])
    all_accounts = await add_account_update_date(all_accounts)
    probs = await ConditionProb.findAll()
    return {
        '__template__': 'condition_prob.html',
        'accounts': all_accounts,
        'prob_amount': len(probs),
        'prob_items_on_page': configs.stock.prob_items_on_page
    }

@asyncio.coroutine
@get('/condition_prob/{page}')
async def get_condition_prob(request, *, page):
    must_log_in(request)
    check_admin(request)
    try:
        page = int(page)
    except ValueError as e:
        raise APIPermissionError()
    probs = await ConditionProb.findAll(orderBy='all_result desc, all_denominator desc', limit=((page-1)*configs.stock.prob_items_on_page, configs.stock.prob_items_on_page))
    if len(probs)>0:
        for prob in probs:
            e1 = prob.e1
            e2 = prob.e2
            e3 = prob.e3
            e4 = prob.e4
            buy_or_follow = prob.buy_or_follow
            if prob.e1 == 1:
                prob.e1 = '<span class="uk-badge uk-badge-success">20日上</span>'
            else:
                prob.e1 = '<span class="uk-badge uk-badge-danger">20日下</span>'

            if prob.e2 == 1:
                prob.e2 = '<span class="uk-badge uk-badge-success">20日上</span>'
            else:
                prob.e2 = '<span class="uk-badge uk-badge-danger">20日下</span>'

            if prob.e3 == 1:
                prob.e3 = '<span class="uk-badge uk-badge-success">上升</span>'
            else:
                prob.e3 = '<span class="uk-badge uk-badge-danger">未上升</span>'

            if prob.e4 == 1:
                prob.e4 = '<span class="uk-badge uk-badge-success">大于前日</span>'
            else:
                prob.e4 = '<span class="uk-badge uk-badge-danger">小于前日</span>'

            if prob.profit == 'E5':
                prob.profit = 'E5:大于90%'
            elif prob.profit == 'E6':
                prob.profit = 'E6:大于60%小于等于90%'
            elif prob.profit == 'E7':
                prob.profit = 'E7:大于30%小于等于60%'
            elif prob.profit == 'E81':
                prob.profit = 'E81:大于25%小于等于30%'
            elif prob.profit == 'E82':
                prob.profit = 'E82:大于20%小于等于25%'
            elif prob.profit == 'E83':
                prob.profit = 'E83:大于15%小于等于20%'
            elif prob.profit == 'E84':
                prob.profit = 'E84:大于10%小于等于15%'
            elif prob.profit == 'E85':
                prob.profit = 'E85:大于5%小于等于10%'
            elif prob.profit == 'E86':
                prob.profit = 'E86:小于等于5%'

            if prob.turnover == 'E9':
                prob.turnover = 'E9:小于等于0.5%'
            elif prob.turnover == 'E10':
                prob.turnover = 'E10:大于0.5%小于等于1%'
            elif prob.turnover == 'E11':
                prob.turnover = 'E11:大于1%小于等于3%'
            elif prob.turnover == 'E12':
                prob.turnover = 'E12:大于3%小于等于5%'
            elif prob.turnover == 'E13':
                prob.turnover = 'E13:大于5%小于等于10%'
            elif prob.turnover == 'E14':
                prob.turnover = 'E14:大于10%小于等于20%'
            elif prob.turnover == 'E15':
                prob.turnover = 'E15:大于20%'

            if prob.increase == 'E16':
                prob.increase = 'E16:小于等于0%'
            if prob.increase == 'E17':
                prob.increase = 'E17:大于0%小于等于2%'
            if prob.increase == 'E18':
                prob.increase = 'E18:大于2%小于等于4%'
            if prob.increase == 'E19':
                prob.increase = 'E19:大于4%小于等于6%'
            if prob.increase == 'E20':
                prob.increase = 'E20:大于6%小于等于9%'
            if prob.increase == 'E21':
                prob.increase = 'E21:大于9%'

            if prob.buy_or_follow == 1:
                prob.buy_or_follow = '<span class="uk-badge uk-badge-danger">买入</span>'
            elif prob.buy_or_follow == 2:
                prob.buy_or_follow = '<span class="uk-badge uk-badge-success">追涨</span>'
            elif prob.buy_or_follow == 3:
                prob.buy_or_follow = '<span class="uk-badge uk-badge-warning">全部</span>'

            high_span = '<span class="uk-badge uk-badge-success">'
            mid_span = '<span class="uk-badge uk-badge-warning">'
            other_span = '<span>'

            all_span = other_span
            if greater_or_close(prob.all_result, 0.9):
                all_span = high_span
            elif greater_or_close(prob.all_result, 0.8):
                all_span = mid_span

            prob.all_success = '%s%s / %s = %s</span>' % (all_span, prob.all_numerator, prob.all_denominator, round_float(prob.all_result, 4))

            profit_span = other_span
            if greater_or_close(prob.profit_result, 0.9):
                profit_span = high_span
            elif greater_or_close(prob.profit_result, 0.8):
                profit_span = mid_span
            prob.profit_success = '%s%s / %s = %s</span>' % (profit_span, prob.profit_numerator, prob.profit_denominator, round_float(prob.profit_result, 4))

            turnover_span = other_span
            if greater_or_close(prob.turnover_result, 0.9):
                turnover_span = high_span
            elif greater_or_close(prob.turnover_result, 0.8):
                turnover_span = mid_span
            prob.turnover_success = '%s%s / %s = %s</span>' % (turnover_span, prob.turnover_numerator, prob.turnover_denominator, round_float(prob.turnover_result, 4))

            increase_span = other_span
            if greater_or_close(prob.increase_result, 0.9):
                increase_span = high_span
            elif greater_or_close(prob.increase_result, 0.8):
                increase_span = mid_span
            prob.increase_success = '%s%s / %s = %s</span>' % (increase_span, prob.increase_numerator, prob.increase_denominator, round_float(prob.increase_result, 4))

            prob.may_buy = get_may_buy(e1, e2, e3, e4, prob.all_result, prob.profit_result, prob.turnover_result, prob.increase_result, prob.all_denominator, buy_or_follow)

    return {
        '__template__': 'condition_prob_records.html',
        'probs': probs
    }

@asyncio.coroutine
@get('/prob_statistical')
async def do_prob_statistica_1(request):
    return await handle_prob_statistical(request, today())

@asyncio.coroutine
@get('/prob_statistical/')
async def do_prob_statistical_2(request):
    return await handle_prob_statistical(request, today())

@asyncio.coroutine
async def handle_prob_statistical(request, date):
    all_accounts = await Account.findAll('user_id=?', [request.__user__.id])
    all_accounts = await add_account_update_date(all_accounts)
    probs = await DailyConditionProb.findAll()
    return {
        '__template__': 'prob_statistical.html',
        'accounts': all_accounts,
        'prob_amount': len(probs),
        'prob_items_on_page': configs.stock.prob_items_on_page,
        'action': '/api/prob_statistical'
    }

def get_may_buy(e1, e2, e3, e4, all_result, profit_result, turnover_result, increase_result, all_denominator, buy_or_follow):
    if all_result == 1 and profit_result > 0.8 and turnover_result > 0.8 and increase_result > 0.8 and all_denominator >= 17:
        may_buy = '<span class="uk-badge uk-badge-danger">全仓买入</span>'
    elif all_result > 0.9 and profit_result > 0.9 and turnover_result > 0.9 and increase_result > 0.9:
        if all_denominator > 37:
            may_buy = '<span class="uk-badge uk-badge-danger">全仓买入</span>'
        elif all_denominator > 10:
            may_buy = '<span class="uk-badge uk-badge-danger">可以买入1/4仓</span>'
        else:
            may_buy = '<span class="uk-badge uk-badge-warning">可以买入1/32仓</span>'
    elif all_result > 0.9 and profit_result > 0.8 and turnover_result > 0.8 and increase_result > 0.8 and all_denominator >= 25:
        may_buy = '<span class="uk-badge uk-badge-danger">可以买入1/2仓</span>'
    elif all_result > 0.9 and profit_result > 0.7 and turnover_result > 0.7 and increase_result > 0.8 and all_denominator > 10:
        if e1 == 1 and (e3 == 1 or e4 == 1):
            may_buy = '<span class="uk-badge uk-badge-warning">可以买入1/8仓</span>'
        else:
            may_buy = '<span class="uk-badge uk-badge-warning">可以买入1/32仓</span>'
    elif all_result > 0.8 and profit_result > 0.7 and turnover_result > 0.7 and increase_result > 0.8 and all_denominator > 10:
        if e1 == 1 and (e3 == 1 or e4 == 1):
            may_buy = '<span class="uk-badge uk-badge-warning">可以买入1/16仓</span>'
        else:
            may_buy = '<span class="uk-badge uk-badge-warning">可以买入1/32仓</span>'
    else:
        may_buy = '不可买'
    return may_buy

@asyncio.coroutine
@get('/prob_statistical/{page}')
async def get_prob_statistical(request, *, page):
    must_log_in(request)
    check_admin(request)
    try:
        page = int(page)
    except ValueError as e:
        raise APIPermissionError()
    probs = await DailyConditionProb.findAll(orderBy='date desc, created_at desc', limit=((page-1)*configs.stock.prob_items_on_page, configs.stock.prob_items_on_page))
    if len(probs)>0:
        for prob in probs:
            dailyIndexE = await DailyIndexE.find(prob.date)
            if dailyIndexE is not None:
                prob.e1, prob.e2, prob.e3, prob.e4 = dailyIndexE.e1, dailyIndexE.e2, dailyIndexE.e3, dailyIndexE.e4

            prob.may_buy = get_may_buy(prob.e1, prob.e2, prob.e3, prob.e4, prob.all_result, prob.profit_result, prob.turnover_result, prob.increase_result, prob.all_denominator, prob.buy_or_follow)

            if prob.e1 == 1:
                prob.e1 = '<span class="uk-badge uk-badge-success">20日上</span>'
            else:
                prob.e1 = '<span class="uk-badge uk-badge-danger">20日下</span>'

            if prob.e2 == 1:
                prob.e2 = '<span class="uk-badge uk-badge-success">20日上</span>'
            else:
                prob.e2 = '<span class="uk-badge uk-badge-danger">20日下</span>'

            if prob.e3 == 1:
                prob.e3 = '<span class="uk-badge uk-badge-success">上升</span>'
            else:
                prob.e3 = '<span class="uk-badge uk-badge-danger">未上升</span>'

            if prob.e4 == 1:
                prob.e4 = '<span class="uk-badge uk-badge-success">大于前日</span>'
            else:
                prob.e4 = '<span class="uk-badge uk-badge-danger">小于前日</span>'

            if prob.profit == 'E5':
                prob.profit = 'E5:大于90%'
            elif prob.profit == 'E6':
                prob.profit = 'E6:大于60%小于等于90%'
            elif prob.profit == 'E7':
                prob.profit = 'E7:大于30%小于等于60%'
            elif prob.profit == 'E81':
                prob.profit = 'E81:大于25%小于等于30%'
            elif prob.profit == 'E82':
                prob.profit = 'E82:大于20%小于等于25%'
            elif prob.profit == 'E83':
                prob.profit = 'E83:大于15%小于等于20%'
            elif prob.profit == 'E84':
                prob.profit = 'E84:大于10%小于等于15%'
            elif prob.profit == 'E85':
                prob.profit = 'E85:大于5%小于等于10%'
            elif prob.profit == 'E86':
                prob.profit = 'E86:小于等于5%'

            if prob.turnover == 'E9':
                prob.turnover = 'E9:小于等于0.5%'
            elif prob.turnover == 'E10':
                prob.turnover = 'E10:大于0.5%小于等于1%'
            elif prob.turnover == 'E11':
                prob.turnover = 'E11:大于1%小于等于3%'
            elif prob.turnover == 'E12':
                prob.turnover = 'E12:大于3%小于等于5%'
            elif prob.turnover == 'E13':
                prob.turnover = 'E13:大于5%小于等于10%'
            elif prob.turnover == 'E14':
                prob.turnover = 'E14:大于10%小于等于20%'
            elif prob.turnover == 'E15':
                prob.turnover = 'E15:大于20%'

            if prob.increase == 'E16':
                prob.increase = 'E16:小于等于0%'
            if prob.increase == 'E17':
                prob.increase = 'E17:大于0%小于等于2%'
            if prob.increase == 'E18':
                prob.increase = 'E18:大于2%小于等于4%'
            if prob.increase == 'E19':
                prob.increase = 'E19:大于4%小于等于6%'
            if prob.increase == 'E20':
                prob.increase = 'E20:大于6%小于等于9%'
            if prob.increase == 'E21':
                prob.increase = 'E21:大于9%'

            if prob.buy_or_follow == 1:
                prob.buy_or_follow = '<span class="uk-badge uk-badge-danger">买入</span>'
            elif prob.buy_or_follow == 2:
                prob.buy_or_follow = '<span class="uk-badge uk-badge-success">追涨</span>'
            elif prob.buy_or_follow == 3:
                prob.buy_or_follow = '<span class="uk-badge uk-badge-warning">全部</span>'

            high_span = '<span class="uk-badge uk-badge-success">'
            mid_span = '<span class="uk-badge uk-badge-warning">'
            other_span = '<span>'

            all_span = other_span
            if greater_or_close(prob.all_result, 0.9):
                all_span = high_span
            elif greater_or_close(prob.all_result, 0.8):
                all_span = mid_span

            prob.all_success = '%s%s / %s = %s</span>' % (all_span, prob.all_numerator, prob.all_denominator, round_float(prob.all_result, 4))

            profit_span = other_span
            if greater_or_close(prob.profit_result, 0.9):
                profit_span = high_span
            elif greater_or_close(prob.profit_result, 0.8):
                profit_span = mid_span
            prob.profit_success = '%s%s / %s = %s</span>' % (profit_span, prob.profit_numerator, prob.profit_denominator, round_float(prob.profit_result, 4))

            turnover_span = other_span
            if greater_or_close(prob.turnover_result, 0.9):
                turnover_span = high_span
            elif greater_or_close(prob.turnover_result, 0.8):
                turnover_span = mid_span
            prob.turnover_success = '%s%s / %s = %s</span>' % (turnover_span, prob.turnover_numerator, prob.turnover_denominator, round_float(prob.turnover_result, 4))

            increase_span = other_span
            if greater_or_close(prob.increase_result, 0.9):
                increase_span = high_span
            elif greater_or_close(prob.increase_result, 0.8):
                increase_span = mid_span
            prob.increase_success = '%s%s / %s = %s</span>' % (increase_span, prob.increase_numerator, prob.increase_denominator, round_float(prob.increase_result, 4))

    return {
        '__template__': 'prob_statistical_records.html',
        'probs': probs
    }

@asyncio.coroutine
@post('/api/prob_statistical')
async def api_prob_statistical(request, *, date, stock_name, profit, turnover, increase, buy_or_follow):
    must_log_in(request)
    check_admin(request)
    if date is None:
        raise APIValueError('date', '日期不能为空')
    if date.strip() == '':
        raise APIValueError('date', '请选择日期')
    date = date.strip()
    if date > today():
        raise APIValueError('date', '日期不能晚于今天')

    dailyIndexE = await DailyIndexE.find(date)

    if dailyIndexE is None:
        raise APIValueError('date', '没有该天的大盘数据')

    e1 = int(dailyIndexE.e1)
    e2 = int(dailyIndexE.e2)
    e3 = int(dailyIndexE.e3)
    e4 = int(dailyIndexE.e4)

    if stock_name is None:
        raise APIValueError('stock_name', '股票名称不能为空')
    if stock_name.strip() == '':
        raise APIValueError('stock_name', '股票名称不能为空')
    stock_name = stock_name.strip()

    stock_inf = get_stock_via_name(stock_name)
    if not stock_inf:
        raise APIValueError('stock_name', '出错了')
    if len(stock_inf)<1:
        raise APIValueError('stock_name', '股票不存在')
    elif len(stock_inf)>1:
        raise APIValueError('stock_name', '股票不唯一')
    stock_code = stock_inf[0]['stock_code']

    if profit is None:
        raise APIValueError('profit', '获利比例不能为空')
    profit = float(profit)
    profit_sign = None
    profit_sign = 'E5' if greater_not_close(profit, 0.9) else profit_sign
    profit_sign = 'E6' if greater_not_close(profit, 0.6) and less_or_close(profit, 0.9) else profit_sign
    profit_sign = 'E7' if greater_not_close(profit, 0.3) and less_or_close(profit, 0.6) else profit_sign
    profit_sign = 'E81' if greater_not_close(profit, 0.25) and less_or_close(profit, 0.3) else profit_sign
    profit_sign = 'E82' if greater_not_close(profit, 0.2) and less_or_close(profit, 0.25) else profit_sign
    profit_sign = 'E83' if greater_not_close(profit, 0.15) and less_or_close(profit, 0.2) else profit_sign
    profit_sign = 'E84' if greater_not_close(profit, 0.1) and less_or_close(profit, 0.15) else profit_sign
    profit_sign = 'E85' if greater_not_close(profit, 0.05) and less_or_close(profit, 0.1) else profit_sign
    profit_sign = 'E86' if greater_or_close(profit, 0) and less_or_close(profit, 0.05) else profit_sign

    if buy_or_follow is None:
        raise APIValueError('buy_or_follow', '追涨买入不能为空')
    buy_or_follow = int(buy_or_follow)

    if buy_or_follow == 1:
        win_percent = 0.04
    else:
        win_percent = 0.034
    lose_percent = 0.1
    lose_cache = 0.005
    days = 30

    if turnover is None or increase is None or turnover.strip() == '' or increase.strip() == '':
        stock_info = get_stock_via_code(stock_code)
        if stock_info == False:
            raise APIValueError('stock_name', '无法获取到股票信息')
        turnover = stock_info[0]['turnover']
        increase = stock_info[0]['increase']
    else:
        turnover = float(turnover)
        increase = float(increase)

    if turnover is None:
        raise APIValueError('stock_name', '无法获取到换手率信息')
    turnover_sign = None
    turnover_sign = 'E9' if turnover is not None and less_or_close(turnover, 0.5) else turnover_sign
    turnover_sign = 'E10' if turnover is not None and greater_not_close(turnover, 0.5) and less_or_close(turnover, 1) else turnover_sign
    turnover_sign = 'E11' if turnover is not None and greater_not_close(turnover, 1) and less_or_close(turnover, 3) else turnover_sign
    turnover_sign = 'E12' if turnover is not None and greater_not_close(turnover, 3) and less_or_close(turnover, 5) else turnover_sign
    turnover_sign = 'E13' if turnover is not None and greater_not_close(turnover, 5) and less_or_close(turnover, 10) else turnover_sign
    turnover_sign = 'E14' if turnover is not None and greater_not_close(turnover, 10) and less_or_close(turnover, 20) else turnover_sign
    turnover_sign = 'E15' if turnover is not None and greater_not_close(turnover, 20) else turnover_sign

    if increase is None:
        raise APIValueError('stock_name', '无法获取到涨跌信息')
    increase_sign = None
    increase_sign = 'E16' if increase is not None and less_or_close(increase, 0) else increase_sign
    increase_sign = 'E17' if increase is not None and greater_not_close(increase, 0) and less_or_close(increase, 2) else increase_sign
    increase_sign = 'E18' if increase is not None and greater_not_close(increase, 2) and less_or_close(increase, 4) else increase_sign
    increase_sign = 'E19' if increase is not None and greater_not_close(increase, 4) and less_or_close(increase, 6) else increase_sign
    increase_sign = 'E20' if increase is not None and greater_not_close(increase, 6) and less_or_close(increase, 9) else increase_sign
    increase_sign = 'E21' if increase is not None and greater_not_close(increase, 9) else increase_sign

    cps = await ConditionProb.findAll('e1=? and e2=? and e3=? and e4=? and profit=? and turnover=? and increase=? and buy_or_follow=?', [e1, e2, e3, e4, profit_sign, turnover_sign, increase_sign, buy_or_follow])

    if cps is None or len(cps)==0:
        raise APIValueError('stock_name', '无法获取到成功率信息')

    if len(cps) > 1:
        raise APIValueError('stock_name', '获取到多条成功率信息')

    dcp = DailyConditionProb(
        date = date,
        stock_code = stock_code,
        stock_name = stock_name,
        profit = profit_sign,
        turnover = turnover_sign,
        increase = increase_sign,
        buy_or_follow = buy_or_follow,
        win_percent = win_percent,
        lose_percent = lose_percent,
        lose_cache = lose_cache,
        days =  days,
        all_numerator =  cps[0].all_numerator,
        all_denominator =  cps[0].all_denominator,
        all_result = cps[0].all_result,
        profit_numerator =  cps[0].profit_numerator,
        profit_denominator =  cps[0].profit_denominator,
        profit_result = cps[0].profit_result,
        turnover_numerator =  cps[0].turnover_numerator,
        turnover_denominator =  cps[0].turnover_denominator,
        turnover_result = cps[0].turnover_result,
        increase_numerator =  cps[0].increase_numerator,
        increase_denominator =  cps[0].increase_denominator,
        increase_result = cps[0].increase_result,
    )

    async with get_pool().get() as conn:
        await conn.begin()
        try:
            await dcp.save(conn)
            await conn.commit()
        except BaseException as e:
            await conn.rollback()
            raise APIValueError('stock_name', '保存信息失败')
    return dcp

@asyncio.coroutine
@post('/api/remove/prob_records')
async def api_remove_prob_record(request, *, prob_id):
    must_log_in(request)
    if not prob_id or not prob_id.strip():
        return '删除记录失败(1)'
    prob_record = await DailyConditionProb.find(prob_id)
    if not prob_record:
        return '删除记录失败(2)'

    async with get_pool().get() as conn:
        await conn.begin()
        try:
            await prob_record.remove(conn)
            await conn.commit()
        except BaseException as e:
            await conn.rollback()
            return '删除记录失败(5)'
    return '删除记录成功'


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

# TODO it's ugly duplicate code. will refactor it later.
@asyncio.coroutine
async def get_recommend(dp):
    dadieweizhidie = False
    dp1 = await DailyParam.findAll('date<=? and increase_range<?', [dp.date, -0.015], orderBy='date desc', limit=1)
    if len(dp1)>0:
        dp2 = await DailyParam.findAll('date>? and increase_range>?', [dp1[0].date, 0], orderBy='date desc', limit=1)
        if len(dp2)==0:
            dadieweizhidie = True 
    # 最大仓位
    max_position = 0
    if dp.stock_market_status == 0:
        max_position = 0.25
        if not dp.big_fall_after_multi_bank_iron:
            max_position = 0.125
    if dp.stock_market_status == 1 or dp.stock_market_status == 2:
        max_position = 1
        if dadieweizhidie or not dp.big_fall_after_multi_bank_iron:
            max_position = 0.5

    clear = dp.shanghai_break_twenty_days_line_obviously or dp.shenzhen_break_twenty_days_line_obviously or dp.shanghai_break_twenty_days_line_for_two_days or dp.shenzhen_break_twenty_days_line_for_two_days or (dp.run_stock_ratio>0.02484 and dp.pursuit_stock_ratio<0.03)

    if clear:
        return '明日务必择机清仓！'

    dp3 = await DailyParam.findAll('date<=?', [dp.date], orderBy='date desc', limit=5)
    pre_state = -1
    flag1 = False
    xiong_to_niu = False
    for d in dp3:
        if d.shanghai_break_twenty_days_line_obviously or d.shenzhen_break_twenty_days_line_obviously or d.shanghai_break_twenty_days_line_for_two_days or d.shenzhen_break_twenty_days_line_for_two_days or (d.run_stock_ratio>0.02484 and d.pursuit_stock_ratio<0.03):
            flag1 = True
        if (d.stock_market_status == 0) and (pre_state == 1 or pre_state == 2):
            xiong_to_niu = True
        pre_state = d.stock_market_status
    dp4 = await DailyParam.findAll('date<=?', [dp.date], orderBy='date desc', limit=2)
    flag2 = False
    for d in dp4:
        if d.pursuit_kdj_die_stock_ratio>=0.5:
            flag2 = True
            break

    flag3 = dp.shanghai_break_twenty_days_line or dp.shenzhen_break_twenty_days_line or dp.pursuit_stock_ratio<0.0036 or dp.strong_pursuit_stock_ratio<0.0018 or (dp.stock_market_status==0 and dp.method2_bigger_9_ratio>0.00155) or flag2
    flag4 = flag1 and not (xiong_to_niu and (dp.stock_market_status == 1 or dp.stock_market_status == 2))
    # 不能买
    cant_buy = dadieweizhidie or dp.four_days_pursuit_ratio_decrease or flag4 or flag3 or (dp.iron_stock_amount>1 or dp.bank_stock_amount>1)
    can_buy_method_1 = (not cant_buy) or ((dadieweizhidie or flag4) and not flag3)
    can_buy_method_2 = not cant_buy

    if not ((can_buy_method_1 and dp.method_1) or (can_buy_method_2 and dp.method_2)):
        return '明日不能买入！'

    # 方式1买入仓位
    if can_buy_method_1 and dp.method_1:
        method1_buy_position = 1/4
        if not cant_buy:
            if not dp.big_fall_after_multi_bank_iron:
                method1_buy_position = method1_buy_position/2
        else:
            if can_buy_method_1 and dadieweizhidie:
                method1_buy_position = method1_buy_position/4
            elif can_buy_method_1:
                method1_buy_position = method1_buy_position/3
            else:
                method1_buy_position = 0

        if method1_buy_position>0:
            return '明日以开盘价买入'+dp.method_1+str(round_float(method1_buy_position*100))+'%仓'
    # 方式2买入仓位
    if can_buy_method_2 and dp.method_2:
        method2_buy_position = 1/16
        if dp.stock_market_status == 0:
            if not can_buy_method_2:
                method2_buy_position = 0
            elif not dp.big_fall_after_multi_bank_iron:
                method2_buy_position = method2_buy_position/2
        if dp.stock_market_status == 1:
            method2_buy_position = 1/10
            if not can_buy_method_2:
                method2_buy_position = 0
        if dp.stock_market_status == 2:
            method2_buy_position = 1/6
            if not can_buy_method_2:
                method2_buy_position = 0

        if method2_buy_position>0:
            return '明日以开盘价买入'+dp.method_2+str(round_float(method2_buy_position*100))+'%仓'
    return '明日不能买入！'