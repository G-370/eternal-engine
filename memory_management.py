import psutil
import os
import time
import gc
import discord
import tracemalloc
import sys

import collections

mems = []
typecounts = collections.Counter()
ONE_MEGABYTE = 1000000
ONE_GIGABYTE = ONE_MEGABYTE * 1000
MEMORY_LIMIT = 3 * ONE_GIGABYTE

def heartbeat():
    ps = psutil.Process(os.getpid())
    meminfo = ps.memory_full_info()
    rss = meminfo.rss

    with open('mems.output', 'at') as mfp:
        mfp.write(f'{rss}\n')

    if (rss / MEMORY_LIMIT >= 1.0):
        print("Memory pressure very high, closing off.")
        sys.exit()
