import asyncio
import random
import time
from loguru import logger
from utils.helpers import get_data_for_token
from src.functions import (
    pool_onchain_balance,
    pool_onchain_listen,
    pool_onchain_alltask
)

class TaskManager:
    def __init__(self, runname) -> None:
        self.runname = runname
        self.datas = get_data_for_token(runname)
        self.count = len(self.datas)
        self.lock = asyncio.Lock()

    async def _launch_task(self, thread: int, runid: int, module_name: str, task_function) -> None:
        while True:
            try:
                async with self.lock:
                    if not self.datas:
                        return 'nokeys'
                    else:
                        data = self.datas.pop(0)
                        id = self.count - len(self.datas)
                # Skip if runid is incorrect
                if runid > 0 and id != runid:
                    continue

                parts = data.split(',')
                if len(parts) < 4:
                    continue
                name,address,type,eth,usdc,usdcmax,proxy = map(str.strip, parts)
                logger.info(f"thread: {thread} id: {id} name: {name} address: {address[:10]} proxy: {proxy}")

                result = await task_function(self.runname, id, name,address,type,eth,usdc,usdcmax,proxy)
                if str(result).find("ERROR") > -1:
                    logger.error(f"thread: {thread} id: {id} name: {name} address: {address[:10]} {module_name} result: {result}")
                    continue
                else:
                    logger.success(f"thread: {thread} id: {id} name: {name} address: {address[:10]} {module_name} result: {result}")

                logger.info(f"thread: {thread} id: {id} name: {name} address: {address[:10]} | Completed account usage")
            except Exception as e:
                logger.error(f"An error occurred in {module_name}: {e}")
                time.sleep(60)

    async def launch_onchain_balance(self, thread: int, runid: int, module_name: str) -> None:
        await self._launch_task(thread, runid, module_name, pool_onchain_balance)

    async def launch_onchain_listen(self, thread: int, runid: int, module_name: str) -> None:
        await self._launch_task(thread, runid, module_name, pool_onchain_listen)

    async def launch_onchain_alltask(self, thread: int, runid: int, module_name: str) -> None:
        await self._launch_task(thread, runid, module_name, pool_onchain_alltask)
