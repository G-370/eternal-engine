from typing import Any, Coroutine
import discord
import discord.gateway
import pymongo
import requests
import re
import datetime
import webhook
import time
import logging
import error_control
import memory_management
import tracemalloc
import os
import sys
from exceptions import *

import traceback
from gc import get_objects
from discord.backoff import ExponentialBackoff
from discord.errors import ConnectionClosed,HTTPException,GatewayNotFound
from discord.gateway import ReconnectWebSocket
from typing import Dict
import asyncio
import aiohttp

tracemalloc.start()

db = pymongo.MongoClient(host='autosystem', port=27027)

guilds_cache = list()

MIRROR_MODE = 'FORUM'
ENVIRON = os.environ.get('DSDENV') or None

class CHANNEL_TYPES:
    GUILD_TEXT = 0
    DM = 1
    GUILD_VOICE = 2
    GROUP_DM = 3
    GUILD_CATEGORY = 4
    GUILD_FORUM = 15

def dsdEE():
    database = 'dsd-eternal-engine'
    if (ENVIRON and len(ENVIRON) >= 1):
        database += ENVIRON
    return db[database]

def slugify(txt: str):
    #regex = re.compile(r"(?![a-zA-Z]).", re.M)
    return re.sub(r"((?![a-zA-Z]).)+", "-", txt.lower())

def setup_data_collection():
    eternal_engine_database = dsdEE()
    return eternal_engine_database.setup_data

def guilds_cache_collection():
    eternal_engine_database = dsdEE()
    return eternal_engine_database.cached_guilds

def guild_forums_collection():
    eternal_engine_database = dsdEE()
    return eternal_engine_database.guild_forums

def guild_forum_threads_collection():
    eternal_engine_database = dsdEE()
    return eternal_engine_database.guild_forum_threads

def guild_forum_webhooks_collection():
    eternal_engine_database = dsdEE()
    return eternal_engine_database.guild_forum_webhooks

def resource_locks_collection():
    eternal_engine_database = dsdEE()
    resource_locks = eternal_engine_database.resource_locks
    return resource_locks

def is_resource_locked(resource, rid):
    lock = resource_locks_collection().find_one({'lock': f'{resource}_{rid}'})
    if lock:
        return lock.get('time', True)
    return None

def lock_resource(resource, rid, time=None):
    payload = {
        'lock': f'{resource}_{rid}'
    }
    if (time and time > 0):
        payload['time'] = time
    resource_locks_collection().insert_one(payload)

def unlock_resource(resource, rid):
    payload = {
        'lock': f'{resource}_{rid}'
    }
    resource_locks_collection().delete_one(payload)

def get_logger_key():
    key = setup_data_collection().find_one({"type": "log_actuator_key"})
    if (key):
        return key.get('value')
    else:
        raise NoLoggerAvailable("Error, no logger key has been setup.")

def get_capture_key():
    key = setup_data_collection().find_one({"type": "capture_key"})
    if (key):
        return key.get('value')
    else:
        raise NoCaptureAvailable("Error, no capture key has been setup.")

def get_guild_category(guild_id: int):
    guild_category_sd = setup_data_collection().find_one({"type": f"guild_category_{guild_id}"})
    if (guild_category_sd is not None):
        return guild_category_sd.get('value')
    else:
        raise NoCategoryAvailable("Categoryless")
    
def get_system_webhook():
    key = setup_data_collection().find_one({"type": "system_webhook"})
    if (key):
        return key.get('value')
    else:
        raise NoSystemWebhook("Error, no system webhook has been setup.")

def insert_guild_category_setup(guild_id: int, category_id: int):
    setup_data_collection().insert_one({
        'type': f"guild_category_{guild_id}",
        'value': category_id
    })

def get_guild_forum(guild_id: int):
    guild_category_sd = guild_forums_collection().find_one({"type": f"guild_forum_{guild_id}"})
    if (guild_category_sd is not None):
        return guild_category_sd.get('value')

def insert_guild_forum(guild_id: int, forum_id: int):
    guild_forums_collection().insert_one({
        'type': f"guild_forum_{guild_id}",
        'value': forum_id
    })

def insert_guild_forum_thread(original_chan: int, thread_chan: int):
    guild_forum_threads_collection().insert_one({
        'type': f"thread_mirror_{original_chan}",
        'value': f"{thread_chan}"
    })

def get_guild_forum_thread(guild_forum_thread_id: int):
    channel_mirror_sd = guild_forum_threads_collection().find_one({"type": f"thread_mirror_{guild_forum_thread_id}"})
    if (channel_mirror_sd is not None):
        return channel_mirror_sd.get('value')

def get_channel_mirror(channel_id: int):
    channel_mirror_sd = setup_data_collection().find_one({"type": f"channel_mirror_{channel_id}"})
    if (channel_mirror_sd is not None):
        return channel_mirror_sd.get('value')

def insert_channel_mirror_setup(original_chan: int, mirror_chan: int):
    setup_data_collection().insert_one({
        'type': f"channel_mirror_{original_chan}",
        'value': f"{mirror_chan}"
    })

def get_channel_mirror_webhook(channel_id: int):
    channel_mirror_webhook_sd = setup_data_collection().find_one({"type": f"channel_mirror_webhook_{channel_id}"})
    if (channel_mirror_webhook_sd is not None):
        return channel_mirror_webhook_sd.get('value')

def insert_channel_mirror_webhook_setup(channel: int, webhook_url: str):
    setup_data_collection().insert_one({
        'type': f"channel_mirror_webhook_{channel}",
        'value': f"{webhook_url}"
    })

def get_forum_mirror_webhook(channel_id: int):
    channel_mirror_webhook_sd = guild_forum_webhooks_collection().find_one({"type": f"channel_mirror_webhook_{channel_id}"})
    if (channel_mirror_webhook_sd is not None):
        return channel_mirror_webhook_sd.get('value')

def insert_forum_mirror_webhook(forum_id, webhook_url: str):
    guild_forum_webhooks_collection().insert_one({
        'type': f"channel_mirror_webhook_{forum_id}",
        'value': f"{webhook_url}"
    })

def from_cache_guild_by_id(gid):
    if (type(gid) != type('')):
        gid = str(gid)
    return guilds_cache_collection().find_one({'id': gid})

def guilds_add_cache(guild_data):

    guilds_cache_collection().find_one_and_update({
        'id': guild_data.get('id')
    }, {
        '$set': {**guild_data, 'last_cache_update': datetime.datetime.now()}
    }, upsert=True)

def where_persist():
    persistor = setup_data_collection().find_one({
        'type': 'target_guild_persistor'
    }) or {}
    return persistor.get('value')

def save_error_capture(ec: error_control.ExceptionCapture):
    payload = ec.as_dict()
    dsdEE().exceptions.insert_one(payload)

class DebuggedSocket(discord.gateway.DiscordWebSocket):
    def send_heartbeat(self, data: Any) -> Coroutine[Any, Any, None]:
        print('\nDOES IT BEAT?\n')
        memory_management.heartbeat()
        return super().send_heartbeat(data)

class CaptureClient(discord.Client):
    async def connect(self, *, reconnect: bool = True) -> None:
        _log = logging.getLogger('CaptureClient')
        backoff = ExponentialBackoff()
        ws_params: Dict[str, Any] = {
            'initial': True,
        }
        while not self.is_closed():
            try:
                coro = DebuggedSocket.from_client(self, **ws_params)
                self.ws = await asyncio.wait_for(coro, timeout=60.0)
                ws_params['initial'] = False
                while True:
                    await self.ws.poll_event()
            except ReconnectWebSocket as e:
                _log.debug('Got a request to %s the websocket.', e.op)
                self.dispatch('disconnect')
                ws_params.update(sequence=self.ws.sequence, resume=e.resume, session=self.ws.session_id)
                if e.resume:
                    ws_params['gateway'] = self.ws.gateway
                continue
            except (
                OSError,
                HTTPException,
                GatewayNotFound,
                ConnectionClosed,
                aiohttp.ClientError,
                asyncio.TimeoutError,
            ) as exc:
                self.dispatch('disconnect')
                if not reconnect:
                    await self.close()
                    if isinstance(exc, ConnectionClosed) and exc.code == 1000:
                        # Clean close, don't re-raise this
                        return
                    raise

                if self.is_closed():
                    return

                # If we get connection reset by peer then try to RESUME
                if isinstance(exc, OSError) and exc.errno in (54, 10054):
                    ws_params.update(
                        sequence=self.ws.sequence,
                        gateway=self.ws.gateway,
                        initial=False,
                        resume=True,
                        session=self.ws.session_id,
                    )
                    continue

                # We should only get this when an unhandled close code happens,
                # such as a clean disconnect (1000) or a bad state (bad token, etc)
                # Sometimes, Discord sends us 1000 for unknown reasons so we should
                # reconnect regardless and rely on is_closed instead
                if isinstance(exc, ConnectionClosed):
                    if exc.code != 1000:
                        await self.close()
                        raise

                retry = backoff.delay()
                _log.exception("Attempting a reconnect in %.2fs", retry)
                await asyncio.sleep(retry)
                # Always try to RESUME the connection
                # If the connection is not RESUME-able then the gateway will invalidate the session
                # This is apparently what the official Discord client does
                ws_params.update(
                    sequence=self.ws.sequence,
                    gateway=self.ws.gateway,
                    resume=True,
                    session=self.ws.session_id,
                )

    def __init__(self, **options: Any) -> None:
        self.logger_actuator: LoggerActuator = LoggerActuator()
        super().__init__(**options)

    async def on_ready(self):
        print('Logged in with ', self.user.name)
        await self.logger_actuator.notice_online_system()

    async def on_message(self, message: discord.Message):
        if (message.guild):
            if (MIRROR_MODE == 'FORUM'):
                guild_forum = self.logger_actuator.grab_guild_forum({
                    'id': message.guild.id,
                    'name': message.guild.name
                })

                mirror_thread = self.logger_actuator.grab_mirrored_channel_forum_mode(guild_forum, {
                    'id': message.channel.id,
                    'name': message.channel.name,
                    'guild_name': message.guild.name
                })

                if (mirror_thread == None):
                    print(f'Dropping forward of message {message.content}, @{message.guild.name}')
                    return None

                mirror_webhook = self.logger_actuator.grab_forum_webhook(guild_forum)
                if (mirror_webhook == None or mirror_webhook == 'None'):
                    print(f'Ignoring message from deactivated webhook chan `{message.channel.name}`, `@{message.guild.name}`, `{message.content}`', )
                    return
                
                try:
                    if (mirror_thread is not None):
                        await webhook.send_message(message, mirror_webhook, thread_id=mirror_thread)
                    else:
                        print(f'Invalid message mirror_thread {mirror_thread}, `{message.channel.name}`, `@{message.guild.name}`, `{message.content}`', )
                except HTTPException as ex:
                    capture = error_control.ExceptionCapture('CaptureClient.on_message;try_catch:webhook.send_message$HTTPException', ex)
                    save_error_capture(capture)
                    pass

            elif (MIRROR_MODE == 'CHANNEL'):
                guild_category = self.logger_actuator.grab_guild_category({
                    'id': message.guild.id,
                    'name': message.guild.name
                })
                mirror_channel = self.logger_actuator.grab_mirrored_channel(guild_category, {
                    'id': message.channel.id,
                    'name': message.channel.name,
                    'guild_name': message.guild.name
                })
                mirror_webhook = self.logger_actuator.grab_channel_webhook(mirror_channel)

                await webhook.send_message(message, mirror_webhook)

class LoggerActuator():
    def __init__(self) -> None:
        self.guilds = {}
        self.host = 'discord.com'
        self.root = 'api'
        self.version = 'v9'
        self.register_current_guilds()

    def api_baseline_url(self, specific_route='', version=None):
        return f'https://{self.host}/{self.root}/{version or self.version}/{specific_route}'

    def register_current_guilds(self):
        for guild in self.get_current_guilds_rq():
            alias = slugify(guild.get('name', f'unknown {guild.get("id")}'))
            self.register_guild(alias, guild.get('id'))

    def register_guild(self, alias, guild_id):
        self.guilds[alias] = guild_id
    
    def do_rq(self, url, method='GET', extra_args={}) -> requests.Response:
        print('doing discord rest request ', url, ' -',  method)
        return requests.request(method=method, url=url, headers={
            'Authorization': f'Bot {get_logger_key()}'
        }, **extra_args)
    
    def get_guild_rq(self, gid):
        url = self.api_baseline_url(f'guilds/{gid}')
        resp = self.do_rq(url)
        return resp.json()
    
    def get_guild(self, gid):
        guild_data = from_cache_guild_by_id(gid)
        if (guild_data is None):
            guild_data = self.get_guild_rq(gid)
            guilds_add_cache(guild_data)
        return guild_data

    def get_current_guilds_rq(self):
        global guilds_cache

        url = self.api_baseline_url('users/@me/guilds')
        resp = self.do_rq(url)
        if (resp.status_code == 200):
            guilds = resp.json()
            return guilds
    
    def create_guild_category_rq(self, guild_id, name):
        url = self.api_baseline_url(f'guilds/{guild_id}/channels')
        resp = self.do_rq(url, 'POST', {
            'json': {
                'name': name,
                'type': CHANNEL_TYPES.GUILD_CATEGORY
            }
        })
        return resp.json()

    def create_guild_forum_rq(self, guild_id, name):
        url = self.api_baseline_url(f'guilds/{guild_id}/channels')

        category = get_guild_category(guild_id)

        resp = self.do_rq(url, 'POST', {
            'json': {
                'name': name,
                'type': CHANNEL_TYPES.GUILD_FORUM,
                'parent_id': int(category) or 1158136849907326996,
                'nsfw': True
            }
        })
        return resp.json()
    
    def grab_guild_category(self, guild_data):
        category = get_guild_category(guild_data.get('id'))
        if (category is None):
            category_resp = self.create_guild_category_rq(where_persist(), slugify(guild_data.get('name')))
            category = category_resp.get('id')
            insert_guild_category_setup(guild_data.get('id'), category)
        return category
    
    def grab_guild_forum(self, guild_data):
        forum = get_guild_forum(guild_data.get('id'))
        if (forum is None):
            forum_resp = self.create_guild_forum_rq(where_persist(), slugify(guild_data.get('name')))
            forum = forum_resp.get('id')
            insert_guild_forum(guild_data.get('id'), forum)
        return forum
    
    def create_guild_channel_rq(self, guild_id, parent_channel, name):
        url = self.api_baseline_url(f'guilds/{guild_id}/channels')
        resp = self.do_rq(url, 'POST', {
            'json': {
                'name': name,
                'type': CHANNEL_TYPES.GUILD_TEXT,
                'parent_id': parent_channel
            }
        })
        return resp.json()
    
    def create_guild_channel_forum_mode_rq(self, forum_channel_id, name, original_channel_id, guild_name):
        resource = 'thread_for_forum'
        resource_id = forum_channel_id

        locked = is_resource_locked(resource, resource_id)
        if (locked):
            print(f'dropping creation of channel_thread for {name} due to locked resource.')
            return None

        url = self.api_baseline_url(f'channels/{forum_channel_id}/threads')
        resp = self.do_rq(url, 'POST', {
            'json': {
                'name': name,
                'message': {
                    'content': f'Archival of all messages in channel {name} or `{original_channel_id}` at guild/server `{guild_name}`'
                },
                'auto_archive_duration': 10080
            }
        })

        time.sleep(2)

        if (resp.status_code == 200 or resp.status_code == 201):
            unlock_resource(resource, resource_id)
        else:
            print('Failed to create forum thread ', resp)
        return resp.json()
    
    def grab_mirrored_channel_forum_mode(self, forum_id, channel_data):
        c_name = channel_data.get('name')
        c_id = channel_data.get('id')
        g_name = channel_data.get('guild_name')
        channel_mirror = get_guild_forum_thread(c_id)
        if (channel_mirror is None):
            resource = ('thread_for_forum', forum_id)

            if (is_resource_locked(*resource)):
                return None

            channel_resp = self.create_guild_channel_forum_mode_rq(forum_id, c_name, c_id, g_name)
            if (channel_resp == None): return None
            response_message = channel_resp.get('message')
            retry_after = channel_resp.get('retry_after')

            if (response_message and retry_after):
                print('We have hit a timeout, locking resource')
                lock_resource(*resource)
                response_retry_after = retry_after or 3
                time.sleep(response_retry_after + 1)
                unlock_resource(*resource)
                print('We waited enough of the timeout, unlocking resource')
            channel_mirror = channel_resp.get('id')
            pass
            insert_guild_forum_thread(c_id, channel_mirror)
        return channel_mirror

    def grab_mirrored_channel(self, category_id, channel_data):
        c_name = channel_data.get('name')
        c_id = channel_data.get('id')
        channel_mirror = get_channel_mirror(c_id)
        if (channel_mirror is None):
            channel_resp = self.create_guild_channel_rq(where_persist(), category_id, slugify(c_name))
            channel_mirror = channel_resp.get('id')
            insert_channel_mirror_setup(c_id, channel_mirror)
        return channel_mirror
    
    def create_channel_webhook_rq(self, channel_id):
        url = self.api_baseline_url(f'channels/{channel_id}/webhooks')
        resp = self.do_rq(url, 'POST', {
            'json': {
                'name': 'Eternal Engine'
            }
        })
        return resp.json()
    
    def grab_forum_webhook(self, forum_channel_id):
        webhook_url = get_forum_mirror_webhook(forum_channel_id)
        if (webhook_url is None):
            webhook_resp = self.create_channel_webhook_rq(forum_channel_id)
            webhook_url = webhook_resp.get('url')
            insert_forum_mirror_webhook(forum_channel_id, webhook_url)
        return webhook_url

    def grab_channel_webhook(self, channel_id):
        webhook_url = get_channel_mirror_webhook(channel_id)
        if (webhook_url is None):
            webhook_resp = self.create_channel_webhook_rq(channel_id)
            webhook_url = webhook_resp.get('url')
            insert_channel_mirror_webhook_setup(channel_id, webhook_url)
        return webhook_url
    
    def send_message(self):
        pass
    
    async def notice_online_system(self):
        await webhook.send_system_message("Back online.", get_system_webhook())
        pass
    async def notice_periodic_system_shutdown(self):
        await webhook.send_system_message("Restarting system...", get_system_webhook())
        pass

def setup_system():
    try:
        lkey = get_logger_key()
        ckey = get_capture_key()
        wpers = where_persist()
        syswh = get_system_webhook()
        if (wpers is None):
            persistless = True
            while persistless:
                newkey = input("In which guild must the glorious bot throw any new servers? gib id> ")
                if (newkey and len(newkey) > 8):
                    setup_data_collection().insert_one({'type': 'target_guild_persistor', 'value': newkey})
                    persistless = False
                    wpers = newkey
                else:
                    print("INVALID")
        cat = get_guild_category(int(wpers))
        
    except NoLoggerAvailable:
        keyless = True
        while keyless:
            newkey = input("You must provide the system with a valid logger key> ")
            if (newkey and len(newkey) > 8):
                setup_data_collection().insert_one({"type": "log_actuator_key", "value": newkey})
                keyless = False
            else:
                print("INVALID")
    except NoCaptureAvailable:
        keyless = True
        while keyless:
            newkey = input("You must provide the system with a valid capture key> ")
            if (newkey and len(newkey) > 8):
                setup_data_collection().insert_one({"type": "capture_key", "value": newkey})
                keyless = False
            else:
                print("INVALID")
    except NoCategoryAvailable:
        keyless = True
        while keyless:
            newkey = input("You must provide the system with a valid category id within the given guild> ")
            if (newkey and len(newkey) > 8):
                setup_data_collection().insert_one({"type": f"guild_category_{wpers}", "value": newkey})
                keyless = False
            else:
                print("INVALID")
    except NoSystemWebhook:
        keyless = True
        while keyless:
            newkey = input("You must provide the system with a webhook for status messages> ")
            if (newkey and len(newkey) > 8):
                setup_data_collection().insert_one({"type": f"system_webhook", "value": newkey})
                keyless = False
            else:
                print("INVALID")


if (__name__ == '__main__'):
    setup_system()
    client = CaptureClient()
    client.run(get_capture_key())