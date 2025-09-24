import os
import re
import platform
import random
import argparse
import asyncio
import datetime
import schedule
import sys
import time
from loguru import logger
from questionary import Choice, select
from termcolor import cprint

from src.functions import (
    gaea_onchain_balance, 
    gaea_onchain_listen,
    gaea_onchain_alltask
)
from src.gaea_client import GaeaClient
from src.task_manager import TaskManager
from utils.helpers import get_data_for_token
from config import get_envsion, set_envsion

MODULE_MAPPING = {
    'gaea_onchain_balance':  gaea_onchain_balance,
    'gaea_onchain_listen':   gaea_onchain_listen,
    'gaea_onchain_alltask':  gaea_onchain_alltask,
    
}
# 预编译正则表达式
PASSWD_REGEX_PATTERN = r'^.*(?=.{8,})(?=.*\d)(?=.*[a-z])(?=.*[A-Z])(?=.*[!@#$%^&*(),.?":{}|<>]).*$'
EMAIL_REGEX_PATTERN = "^[a-zA-Z0-9_+&*-]+(?:\\.[a-zA-Z0-9_+&*-]+)*@(?:[a-zA-Z0-9-]+\\.)+[a-zA-Z]{2,7}$"
# ----------------------------------------------------------------------------------------------------------

def is_id_valid(id, runeq, rungt, runlt):
    match = False
    if runeq != 0:
        match |= (id == runeq)
    if rungt != 0 and runlt != 0:
        match |= (rungt < id < runlt)
    elif rungt != 0:
        match |= (id > rungt)
    elif runlt != 0:
        match |= (id < runlt)
    elif runeq == 0 and rungt == 0 and runlt == 0:
        match |= True
    return match

async def limit_concurrency(semaphore, func, **kwargs):
    async with semaphore:
        return await func(**kwargs)

async def gaea_run_module_multiple_times(module, count, runname, id, name,address,type,eth,usdc,usdcmax, proxy):
    delay = random.randint(5, 10)
    logger.debug(f"id: {id} name: {name} address: {address} account delay: {delay} seconds")
    await asyncio.sleep(delay)
    
    # 循环
    while True:
        # 开始执行当前任务
        result = await module(runname, id, name,address,type,eth,usdc,usdcmax, proxy)
        logger.debug(f"id: {id} name: {name} address: {address} result: {result}")
        
        if module == gaea_onchain_listen:
            # 等待进入下一次
            delay = random.randint(1800, 2400) # 30-40分钟循环
            logger.info(f"id: {id} name: {name} address: {address} task delay: {delay} seconds")
            await asyncio.sleep(delay)
        else: # 不循环
            break

async def gaea_run_modules(module, runname, runeq, rungt, runlt, runthread):
    datas = get_data_for_token(runname)
    logger.info(f"runname: {runname} runeq: {runeq} rungt: {rungt} runlt: {runlt}")

    if runthread<=0:
        runthread = sum(1 for id, _ in enumerate(datas, start=1) if is_id_valid(id, runeq, rungt, runlt))
        # logger.debug(f"runthread: {runthread}")
    runthread = min(runthread, 10)
    logger.info(f"runname: {runname} runthread: {runthread}")
    semaphore = asyncio.Semaphore(runthread)

    count=0
    tasks = []
    for data_id, data in enumerate(datas, start=1):
        if not is_id_valid(data_id, runeq, rungt, runlt):
            continue

        parts = data.split(',')
        if len(parts) < 7:
            logger.error(f"Invalid data: ({len(parts)}){data}")
            continue

        name,address,type,eth,usdc,usdcmax,proxy = map(str.strip, parts)
        # logger.debug(f"parts: {parts}")

        if proxy == 'proxy':
            logger.error(f"Invalid proxy: {proxy}")
            continue

        count+=1
        logger.debug(f"run task_id: {data_id} create gaea_run_modules task")
        tasks.append(asyncio.create_task(
            limit_concurrency(
                semaphore,
                gaea_run_module_multiple_times,
                module=module,
                count=count,
                runname=runname,
                id=data_id,
                name=name,
                address=address,
                type=type,
                eth=eth,
                usdc=usdc,
                usdcmax=usdcmax,
                proxy=proxy
            )
        ))
    try:
        await asyncio.gather(*tasks)
    except asyncio.CancelledError:
        logger.warning("Tasks were cancelled.")
    except Exception as e:
        logger.error(f"Error occurred while running tasks: {e}")

def run_module(module, runname, runeq, rungt, runlt, runthread):
    asyncio.run(gaea_run_modules(module=module, runname=runname, runeq=runeq, rungt=rungt, runlt=runlt, runthread=runthread))

def main(runname, runeq, rungt, runlt, runthread):
    try:
        while True:
            if platform.system().lower() == 'windows':
                os.system("title main")
            answer = select(
                'Choose',
                choices=[
                    Choice("🔥 Gaea onchain tasks - balance",    'gaea_onchain_balance',  shortcut_key="1"),
                    Choice("🚀 Gaea onchain tasks - listen",     'gaea_onchain_listen',   shortcut_key="2"),
                    Choice("🚀 Gaea onchain tasks - alltask",    'gaea_onchain_alltask',  shortcut_key="3"),
                    Choice('❌ Exit', "exit", shortcut_key="0")
                ],
                use_shortcuts=True,
                use_arrow_keys=True,
            ).ask()

            if answer in MODULE_MAPPING:
                run_module(MODULE_MAPPING[answer], runname, runeq, rungt, runlt, runthread)
            elif answer == 'exit':
                sys.exit()
    except (KeyboardInterrupt, asyncio.CancelledError, SystemExit) as e:
        cprint(f"\nShutting down due to: {type(e).__name__}", color='light_yellow')
        sys.exit()

# ----------------------------------------------------------------------------------------------------------

# ----------------------------------------------------------------------------------------------------------

async def gaea_daily_task_modules(module, runname, runeq, runthread):
    module_mapping = {
        gaea_onchain_balance:  "launch_onchain_balance",
        gaea_onchain_listen:   "launch_onchain_listen",
        gaea_onchain_alltask:  "launch_onchain_alltask",
    }
    module_name = module_mapping.get(module, "none")

    if runthread==0:
        datas = get_data_for_token(runname)
        runthread=len(datas)
    if int(runeq)>0:
        runthread=1

    tasks = []
    task_manager = TaskManager(runname)
    for thread in range(1, runthread+1):
        delay = random.randint(10, 20)
        logger.debug(f"func: {module_name} thread: {thread} delay: {delay} seconds")
        await asyncio.sleep(delay)

        # logger.info(f"func: {module_name} thread: {thread} runeq: {runeq} module: {module_name}")
        task_func = getattr(task_manager, module_name, None)
        tasks.append(asyncio.create_task(
            task_func(thread, runeq, module_name)
        ))

    await asyncio.gather(*tasks)

def daily_task_module():
    logger.info("Execute alltask scheduled task...")
    asyncio.run(gaea_daily_task_modules(module=gaea_onchain_alltask, runname=run_name, runeq=run_eq, runthread=run_thread))

def main_task(run_hour: int):
    # 获取当前时间
    current_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    logger.info(f"current_time: {current_time}")
    # 设置定时任务
    if run_hour==0:
        run_hour = datetime.datetime.now().hour
        run_minute = datetime.datetime.now().minute
        task_time = f"{str(run_hour).zfill(2)}:{str(random.randint(run_minute, 59)).zfill(2)}"
    else:
        task_time = f"{str(run_hour).zfill(2)}:{str(random.randint(0, 59)).zfill(2)}"
    logger.info(f"The scheduled task will start at {task_time} every day ...")
    schedule.every().day.at(task_time).do(daily_task_module)

# ----------------------------------------------------------------------------------------------------------

if __name__ == '__main__':
    # 初始化参数
    parser = argparse.ArgumentParser()
    parser.add_argument('-a', '--auto', type=bool, default=False, action=argparse.BooleanOptionalAction)
    parser.add_argument('-r', '--run', type=int, default=0)
    parser.add_argument('-d', '--debug', type=bool, default=False, action=argparse.BooleanOptionalAction)
    parser.add_argument('-n', '--name', type=str, default='')
    parser.add_argument('-e', '--equal', type=int, default=0)
    parser.add_argument('-g', '--greater', type=int, default=0)
    parser.add_argument('-l', '--less', type=int, default=0)
    parser.add_argument('-t', '--thread', type=int, default=0)
    args = parser.parse_args()
    run_auto = bool(args.auto)
    run_run = int(args.run)
    run_debug = bool(args.debug)
    run_name = str(args.name)
    run_eq = int(args.equal)
    run_gt = int(args.greater)
    run_lt = int(args.less)
    run_thread = int(args.thread)

    # 日志级别
    log_level = "DEBUG" if run_debug else "INFO"
    logger.remove()
    logger.add(sys.stdout, level=log_level)
    # logger.add("data/logs/logging.log", rotation="100 MB", level=log_level)

    if run_auto:
        if 0 <= run_run <= 23:
            main_task(run_run)
        else:
            logger.error(f"Invalid parameter, run: {run_run} must be between 0 and 23.")
            sys.exit(1)

        # 无限循环，以便定时任务能够持续运行
        while True:
            schedule.run_pending()
            time.sleep(1)
    else:
        logger.info("Start now ...")
        main(run_name, run_eq, run_gt, run_lt, run_thread)
        logger.info("All wallets completed their tasks!")
