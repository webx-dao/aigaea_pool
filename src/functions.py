import os
import platform
from src.gaea_client import GaeaClient
from src.gaea_dailytask import GaeaDailyTask

# gaea

async def gaea_onchain_balance(runname, id, name,address,type,eth,usdc,usdcmax, proxy):
    if platform.system().lower() == 'windows':
        os.system("title gaea-balance")
    daily_task = GaeaDailyTask(GaeaClient(runname=runname, id=id, name=name, address=address, type=type, eth=eth, usdc=usdc, usdcmax=usdcmax, proxy=proxy))
    return await daily_task.daily_onchain_balance()

async def gaea_onchain_listen(runname, id, name,address,type,eth,usdc,usdcmax, proxy):
    if platform.system().lower() == 'windows':
        os.system("title gaea-listen")
    daily_task = GaeaDailyTask(GaeaClient(runname=runname, id=id, name=name, address=address, type=type, eth=eth, usdc=usdc, usdcmax=usdcmax, proxy=proxy))
    return await daily_task.daily_onchain_listen()

async def gaea_onchain_alltask(runname, id, name,address,type,eth,usdc,usdcmax, proxy):
    if platform.system().lower() == 'windows':
        os.system("title gaea-alltask")
    daily_task = GaeaDailyTask(GaeaClient(runname=runname, id=id, name=name, address=address, type=type, eth=eth, usdc=usdc, usdcmax=usdcmax, proxy=proxy))
    return await daily_task.daily_onchain_alltask()
