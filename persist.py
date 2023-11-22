import logging
from logging import LogRecord
import json
import pymongo
import datetime

conn = pymongo.MongoClient(host='autosystem', port=27027)
dsd_db = conn['ee-dsd-db']
gateway = dsd_db.gateway

class DiscordEventHandler(logging.Handler):
    def emit(self, record: LogRecord) -> None:
        if (record.funcName == 'received_message'):
            if (type(record.args) is dict and record.args.get('op') == 0):
                dispatch_type = record.args.get('t')
                dispatch_data = record.args.get('d')

                dataset = {
                    'ts': str(datetime.datetime.now()),
                    't': dispatch_type,
                    'd': dispatch_data,
                    's': 'eternal-engine'
                }

                if (dispatch_type == 'MESSAGE_CREATE'):
                    pass
                
                gateway.insert_one(dataset)