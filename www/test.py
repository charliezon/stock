# import orm
# from models import User
# from orm import create_pool,destory_pool
# import asyncio
# from config import configs

# loop = asyncio.get_event_loop()

# @asyncio.coroutine
# async def test():
#     await orm.create_pool(loop, user=configs.db.user, password=configs.db.password, db=configs.db.db)
#     u = User(name='B', email='b@example.com', passwd='1234567890', image='about:blank')
#     await u.save()
#     await destory_pool()

# loop.run_until_complete(test())
# loop.close()

import decimal
from decimal import Decimal

from models import round_float
context=decimal.getcontext() # 获取decimal现在的上下文
context.rounding = decimal.ROUND_05UP

# print(round(Decimal(2.55), 1)) # 2.6
# print(format(Decimal(2.55), '.1f')) #'2.6'
# print(round(Decimal(3276.9996), 0))
print(round_float(2.55, 1))
print(round_float(2.55))
print(round_float(3276.234, 2))
print(round_float(3276.234, 1))
print(round_float(3276.9996, 1))
print(round_float(3276.9996, 2))
print(round_float(3276.9996, 3))
print(round_float(3276.9996, 4))
