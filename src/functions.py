import os
import platform
from src.pool_client import PoolClient
from src.pool_dailytask import PoolDailyTask

# Pool

async def pool_onchain_balance(runname, id, name,address,type,eth,usdc,usdcmax, proxy):
    if platform.system().lower() == 'windows':
        os.system("title Pool-balance")
    daily_task = PoolDailyTask(PoolClient(runname=runname, id=id, name=name, address=address, type=type, eth=eth, usdc=usdc, usdcmax=usdcmax, proxy=proxy))
    return await daily_task.daily_onchain_balance()

async def pool_onchain_listen(runname, id, name,address,type,eth,usdc,usdcmax, proxy):
    if platform.system().lower() == 'windows':
        os.system("title Pool-listen")
    daily_task = PoolDailyTask(PoolClient(runname=runname, id=id, name=name, address=address, type=type, eth=eth, usdc=usdc, usdcmax=usdcmax, proxy=proxy))
    return await daily_task.daily_onchain_listen()

async def pool_onchain_alltask(runname, id, name,address,type,eth,usdc,usdcmax, proxy):
    if platform.system().lower() == 'windows':
        os.system("title Pool-alltask")
    daily_task = PoolDailyTask(PoolClient(runname=runname, id=id, name=name, address=address, type=type, eth=eth, usdc=usdc, usdcmax=usdcmax, proxy=proxy))
    return await daily_task.daily_onchain_alltask()
