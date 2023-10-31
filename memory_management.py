import psutil
import os
import time
import gc
import discord
import tracemalloc

import collections

mems = []
typecounts = collections.Counter()

def heartbeat():
    ps = psutil.Process(os.getpid())
    meminfo = ps.memory_full_info()
    rss = meminfo.rss

    with open('mems.output', 'at') as mfp:
        mfp.write(f'{rss}\n')