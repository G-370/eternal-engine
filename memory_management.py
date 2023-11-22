import psutil
import os
import time
import gc
import discord
import tracemalloc
import sys
import asyncio
from exceptions import *

import collections
from engine import LoggerActuator

mems = []
typecounts = collections.Counter()
ONE_MEGABYTE = 1000000
ONE_GIGABYTE = ONE_MEGABYTE * 1000
MEMORY_LIMIT = 2 * ONE_GIGABYTE


# If return True, then we kill the system
def heartbeat():
    ps = psutil.Process(os.getpid())
    meminfo = ps.memory_full_info()
    rss = meminfo.rss

    with open('mems.output', 'at') as mfp:
        mfp.write(f'{rss}\n')

    if (rss / MEMORY_LIMIT >= 1.0):
        print("Memory pressure very high, closing off.")
        async def notice():
            await LoggerActuator().notice_periodic_system_shutdown()

        loop = asyncio.get_event_loop()
        coroutine = notice()
        loop.run_until_complete(coroutine)
        sys.exit()
        #raise HighMemoryUsage("Higher than 3 gigabytes of ram being used.")