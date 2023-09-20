from typing import Any
import discord
import pymongo
import requests
import re
import datetime
import webhook

db = pymongo.MongoClient(host='autosystem', port=27027)

guilds_cache = list()

class CHANNEL_TYPES:
    GUILD_TEXT = 0
    DM = 1
    GUILD_VOICE = 2
    GROUP_DM = 3
    GUILD_CATEGORY = 4

def slugify(txt: str):
    #regex = re.compile(r"(?![a-zA-Z]).", re.M)
    return re.sub(r"((?![a-zA-Z]).)+", "-", txt.lower())

def setup_data_collection():
    eternal_engine_database = db['dsd-eternal-engine']
    return eternal_engine_database.setup_data

def guilds_cache_collection():
    eternal_engine_database = db['dsd-eternal-engine']
    return eternal_engine_database.cached_guilds

def get_logger_key():
    key = setup_data_collection().find_one({"type": "log_actuator_key"})
    if (key):
        return key.get('value')

def get_capture_key():
    key = setup_data_collection().find_one({"type": "capture_key"})
    if (key):
        return key.get('value')

def get_guild_category(guild_id: int):
    guild_category_sd = setup_data_collection().find_one({"type": f"guild_category_{guild_id}"})
    if (guild_category_sd is not None):
        return guild_category_sd.get('value')

def insert_guild_category_setup(guild_id: int, category_id: int):
    setup_data_collection().insert_one({
        'type': f"guild_category_{guild_id}",
        'value': category_id
    })

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

class CaptureClient(discord.Client):
    def __init__(self, **options: Any) -> None:
        self.logger_actuator: LoggerActuator = LoggerActuator()
        super().__init__(**options)

    async def on_ready(self):
        print('Logged in with ', self.user.name)

    async def on_message(self, message: discord.Message):
        if (message.guild):
            guild_category = self.logger_actuator.grab_guild_category({
                'id': message.guild.id,
                'name': message.guild.name
            })
            mirror_channel = self.logger_actuator.grab_mirrored_channel(guild_category, {
                'id': message.channel.id,
                'name': message.channel.name
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
    
    def grab_guild_category(self, guild_data):
        category = get_guild_category(guild_data.get('id'))
        if (category is None):
            category_resp = self.create_guild_category_rq(where_persist(), slugify(guild_data.get('name')))
            category = category_resp.get('id')
            insert_guild_category_setup(guild_data.get('id'), category)
        return category
    
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

    def grab_channel_webhook(self, channel_id):
        webhook_url = get_channel_mirror_webhook(channel_id)
        if (webhook_url is None):
            webhook_resp = self.create_channel_webhook_rq(channel_id)
            webhook_url = webhook_resp.get('url')
            insert_channel_mirror_webhook_setup(channel_id, webhook_url)
        return webhook_url

client = CaptureClient()
client.run(get_capture_key())