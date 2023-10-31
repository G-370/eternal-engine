from discord.errors import HTTPException
import traceback
import datetime
import gc

ERROR_CONTROL_TRACKING = list()

error_count_accumulation_buffer = 0

GC_COUNTS = list()
GC_OBJ_STR = list()

def accumulation_ping():
    print('We have reached a error collection threshold, truly truly the errors of all time.')
    counts = gc.get_count()
    # 148, 6, 9
    # 237, 2, 2
    print('The counts for gc are: ', counts)
    ttt = str()
    objstrs = [ obj for obj in gc.get_objects()]
    print('\n The Objects inside of the GC are: ', objstrs, '\n')
    GC_OBJ_STR.append(objstrs)
    GC_COUNTS.append(counts)
    pass
    

def track_count(etype: str):
    global ERROR_CONTROL_TRACKING, error_count_accumulation_buffer
    ERROR_CONTROL_TRACKING.append([datetime.datetime.now().timestamp(), etype])

    error_count_accumulation_buffer += 1

    if (error_count_accumulation_buffer >= 10):
        accumulation_ping()
        error_count_accumulation_buffer = 0

class ExceptionCapture():
    def http_exception_metadata(self):
        ex = self.exception
        exception_metadata = {
            'request': {
                'url': str(ex.response.request_info.url),
                'method': str(ex.response.request_info.method)
            },
            'response_data': ex.json
        }
        return exception_metadata

    def type_identifier(self):
        typestr = ''
        typestr += self.app_type
        if (self.source_type):
            typestr += f'___{self.source_type}'
        return typestr

    def __init__(self, app_type: str, ex: Exception) -> None:
        self.exception = ex

        self.app_type = app_type
        self.traceback = traceback.format_exc()
        self.captured_at_ts = datetime.datetime.now().timestamp()
        self.captured_at = str(datetime.datetime.now())

        self.metadata = None
        self.source_type = None
        self.message = ''

        if (isinstance(ex, HTTPException)):
            self.source_type = 'discord.errors.HTTPException'
            self.metadata = self.http_exception_metadata()
            self.message = ex.text

        track_count(self.type_identifier())
    
    def as_dict(self):
        return {
            'app_type': self.app_type,
            'source_type': self.source_type,
            'message': self.message,
            'traceback': self.traceback,
            'captured_at_raw': self.captured_at_ts,
            'captured_at': self.captured_at,
            'metadata': self.metadata
        }
