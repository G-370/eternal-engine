import discord
import discord.abc
import re
import aiohttp
import asyncio
import requests

USER_MENTION_PATTERN = re.compile('(\<@(\d*)\>)')
SAMPLE = "Hello <@1158144160923140108> and also <@740408220325118004> and maybe <@<@<@<@740408220325118004>"

class Thread:
    def __init__(self, thread_id) -> None:
        self.id = thread_id
        
def depingify(matched: re.Match):
    lr = matched.regs[-1]
    striped: str = matched.string[lr[0]:lr[1]]
    return f'`ping {striped}`'

async def send_system_message(cnt, target_webhook):
    async with aiohttp.ClientSession() as session:
        hook = discord.Webhook.from_url(target_webhook, session=session)
        payload = {
            'content': cnt
        }
        await hook.send(**payload)


async def send_message(msg: discord.Message, target_webhook, thread_id = None):
    async with aiohttp.ClientSession() as session:
        hook = discord.Webhook.from_url(target_webhook, session=session)
        avatar_url = msg.author.display_avatar.url
        embeds = msg.embeds

        files = [ await ath.to_file() for ath in msg.attachments] or []
        mediabeds = ''

        for emb in embeds:
            mediabeds += f"\n{emb.url}"
            
        raw_content = (msg.content or '[media]') + mediabeds
        
        pingless_content = re.sub(USER_MENTION_PATTERN, depingify, raw_content)

        payload = {
            'content': pingless_content,
            'avatar_url': avatar_url,
            'embeds': embeds,
            'username':  f'{msg.author.name} @{msg.author.id}'
        }

        if (thread_id):
            thread = Thread(thread_id)
            res = await hook.send(**payload, files=files, thread=thread)
            pass
        else:
            await hook.send(**payload, files=files)

if (False): #Test Case
    re.sub(USER_MENTION_PATTERN, depingify, SAMPLE)