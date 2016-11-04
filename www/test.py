import orm
from models import User
from orm import create_pool,destory_pool
import asyncio

loop = asyncio.get_event_loop()

@asyncio.coroutine
async def test():
    await orm.create_pool(loop, user='root', password='rootroot', db='stock')
    u = User(name='Test', email='test@example.com', passwd='1234567890', image='about:blank')
    await u.save()
    await destory_pool()

loop.run_until_complete(test())
loop.close()