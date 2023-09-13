import json
import discord
import asyncio
import random
import datetime
import aiohttp
from pymongo import MongoClient

SOURCE_COMMAND_CHANNEL = 1120473346405044424
TARGET_DISCORD = 1127376659713101906 # 1127354231637147660 - Aspien logger thread, A channel or thread
WH_ETERNAL_ENGINE_MAIN = 'https://discord.com/api/webhooks/1127382546540412948/lzaJRtQlzD2Dx_sS2YnGfm0wDRjX4cm2MSPpAhCETgZXThffo2Dsgxy3mdZEL4s38U4Y'
WH_ETERNAL_ENGINE_CHANGES = 'https://discord.com/api/webhooks/1150864918627745922/9TzpXW78paEDFbV75eBf5S9GpoCyVf6Gn-ohrhlMIPTQxGLyZt1GwHPNg_fcGYxPjwlX'
CONFIG_FILE = '.env.json'
SOURCE_GUILD = 845304829077225472 #1106206049528201256 #845304829077225472

CONTROL_ROLES = [] #[950670496683413504, 1018403524196978719]

environment = json.load(open(CONFIG_FILE, 'r'))
TOKEN = environment['TOKEN'] if 'TOKEN' in environment else None
CONNECTION = environment['CONNECTION'] if 'CONNECTION' in environment else None

PERSIST_FLAGS = ['DWEBHOOK'] # DCHANNEL, MONGO, DWEBHOOK

if (not TOKEN):
    raise ValueError()

def serialize_complex(obj):
    return obj.to_dict()

deletion = []
# In Hours
delete_after = 24

def get_database():
    client = MongoClient(CONNECTION)
    return client['logballs']

def check_expiry(client: discord.Client):
    global deletion
    global delete_after

class LoggerClient(discord.Client):
    async def on_ready(self):
        print('Logged in with ', self.user.name)

    async def notify(self, content: str, notification_type: str = 'UNK'):
        now = datetime.datetime.now().isoformat()
        content = f'`- Captured {now} `\n' + content
        if ('DCHANNEL' in PERSIST_FLAGS):
            await self.send_message_discord(content)
        if ('DWEBHOOK' in PERSIST_FLAGS):
            print('NOTIF TYPE', notification_type)
            if (notification_type == 'DELETED_MESSAGE'):
                await self.send_webhook_discord(content)
            else:
                await self.forward_wh(content, WH_ETERNAL_ENGINE_CHANGES)
        if ('MONGO' in PERSIST_FLAGS):
            await self.send_mongodb(content)

    async def send_webhook_discord(self, content: str):
        async with aiohttp.ClientSession() as session:
            hook = discord.Webhook.from_url(WH_ETERNAL_ENGINE_MAIN, session=session)
            await hook.send(content)
    
    async def forward_wh(self, content: str, wh: str = WH_ETERNAL_ENGINE_MAIN):
        async with aiohttp.ClientSession() as session:
            hook = discord.Webhook.from_url(wh, session=session)
            await hook.send(content)
    
    async def send_mongodb(self, content: str):
        db = get_database()
        col = db['eternal-engine']
        col.insert_one({'str': content})
        await asyncio.sleep(1)

    async def send_message_discord(self, content: str):
        target = self.get_channel(TARGET_DISCORD)
        async with target.typing():
            sleeps = random.randint(1,6)
            print('sleep ', sleeps)
            await asyncio.sleep(sleeps)
            await target.send(content)
    
    async def on_message_edit(self, before: discord.Message, after: discord.Message):
        #if (before.author.id == self.user.id): return
        if (before.guild and ((SOURCE_GUILD is not None) and before.guild.id != SOURCE_GUILD)): return

        content_before = before.content
        content_after = after.content
        embeds_before = before.embeds
        embeds_after = after.embeds
        attachments_before = before.attachments
        attachments_after = after.attachments

        content_changed = content_before != content_after
        embeds_changed = len(embeds_after) != len(embeds_before)
        attachments_changed = len(attachments_before) != len(attachments_after)

        if (content_changed or embeds_changed or attachments_changed):
            notice = f'# Message Changed {after.id}\n- {after.jump_url}\n'
            if (content_changed):
                notice += f'- Content change\n  - *before* \n    - {content_before}\n  - *after* \n    - {content_after}\n'
            if (embeds_changed):
                notice += f'- Embed quantity changed\n  - *before* {len(embeds_before)}\n  - *after* {len(embeds_after)}\n'
            if (attachments_changed):
                notice += f'- Attachment quantity changed\n  - *before* {len(attachments_before)}\n - *after* {len(attachments_after)}\n'
        
            print('Logged changed message')
            await self.notify(notice)

    async def on_message_delete(self, message: discord.Message):
        if (message.guild and ((SOURCE_GUILD is None) or message.guild.id == SOURCE_GUILD)):
            deleted_dict = message.to_message_reference_dict()
            author = message.author
            payload = {
                'content': message.content + '\n',
                'created': str(message.created_at),
                'author_identity': f'{author.name}#{author.discriminator} {author.display_name} ({author.id})',
                'embeds': json.loads(json.dumps(message.embeds, indent=2, default=serialize_complex)),
                'attachments': json.loads(json.dumps(message.attachments, indent=2, default=serialize_complex)),
                'last_edited': str(message.edited_at),
                'channel': message.channel.name,
                'channel_id': message.channel.id,
                'guild': message.guild.name,
                'guild_id': message.guild.id,
                'source': 'LOGBALLS_MSG_BOT'
            }

            message = f'# Message Deleted {message.id}\n'
            message += f'<@{author.id}>\n'
            message += '```json\n'
            message += json.dumps(payload, indent=2)
            message += '```'

            print('Logged deleted message')
            await self.notify(message, 'DELETED_MESSAGE')

    async def help_command(self, message: discord.Message, args):
        output = ''
        output += '### Loggerbot Commands\n'
        output += '- *help* \n  - shows this\n'
        output += '- *time* \n  - shows after how many hours a log is deleted\n'
        output += '- *time value* \n  - sets after how many hours a log is deleted\n'
        output += '- *clear* \n  - deletes ALL log messages\n'
        output += '- *shadap* \n  - OwO bot machinery stops logging `~.~`\n'
        output += '- *gocrazy* \n  - OuO LOGBALLS NOW LOGBALLING!!\n'
        output += '\n ```LOGBALLS_MSG_BOT```'
        await message.reply(output)
    
    async def time_command(self, message: discord.Message, args):
        output = ''

        global delete_after

        match args:
            case [value]:
                try:
                    val = float(value)
                    if (val > 0):
                        delete_after = val
                    else:
                        raise ValueError()
                except BaseException:
                    output += 'Hey! that is not possible... only numbers above zero!\n'

        output = f'After {delete_after} hours I will delete a log'

        await message.reply(output)

    async def clear_command(self, message: discord.Message, args):
        content = ''

        message.reply('Oh... this might take a while, please wait.')

    async def handle_command(self, message, command):
        match command.split(' '):
            case ['help', *args]: await self.help_command(message, args)
            case ['time', *args]: await self.time_command(message, args)

    async def on_message(self, message: discord.Message):
        pass
        # if (message.guild and message.guild.id == GUILD):
        #     if (message.channel and message.channel.id == CHANNEL_ID):
        #         if (message.content.strip().startswith('~~')):
        #             author_ids = message.author._roles.tolist()
        #             role_intersection = [rid for rid in CONTROL_ROLES if rid in author_ids]
        #             is_controller = len(role_intersection) > 0

        #             if (not is_controller):
        #                 content_raw = message.content.replace('~~', '').strip()
        #                 await self.handle_command(message, content_raw)
        #             else:
        #                 info_control_roles = []
        #                 for role_id in CONTROL_ROLES:
        #                     info_control_roles.append(message.guild.get_role(role_id))
        #                 name_control_roles = ' or '.join([role.name for role in info_control_roles])
        #                 await message.reply(f"I am sorry but you're not {name_control_roles}")

clientInstance = LoggerClient()
clientInstance.run(TOKEN)