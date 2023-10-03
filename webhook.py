import discord
import discord.abc
import aiohttp
import asyncio
import requests

class Thread:
    def __init__(self, thread_id) -> None:
        self.id = thread_id

async def send_message(msg: discord.Message, target_webhook, thread_id = None):
    async with aiohttp.ClientSession() as session:
        hook = discord.Webhook.from_url(target_webhook, session=session)
        avatar_url = msg.author.display_avatar.url
        embeds = msg.embeds

        files = [ await ath.to_file() for ath in msg.attachments] or []
        mediabeds = ''

        for emb in embeds:
            mediabeds += f"\n{emb.url}"

        # for ath in attachments:
        #     emby = discord.Embed(url=ath, description=ath, title='Media')
        #     embeds.append(emby)
        #     mediabeds += f"\n{ath}"

        payload = {
            'content': (msg.content or '[media]') + mediabeds,
            'avatar_url': avatar_url,
            'embeds': embeds,
            'username':  f'{msg.author.name} @{msg.author.id}'
        }

        # print(f'ORIGINALRU GOES BRRRRR', {
        #     'author': '\n'.join([
        #         msg.author.guild_avatar and msg.author.guild_avatar.url or '',
        #         msg.author.default_avatar and msg.author.default_avatar.url or '',
        #         msg.author.display_avatar and msg.author.display_avatar.url or ''
        #     ] or ['']),
        #     'embeds': '\n'.join([
        #         embed.url or '' for embed in msg.embeds
        #     ] or ['']),
        #     'attachments': '\n'.join([
        #         ath.url or '' for ath in msg.attachments
        #     ] or [''])
        # })

        if (thread_id):
            thread = Thread(thread_id)
            res = await hook.send(**payload, files=files, thread=thread)
            pass
        else:
            await hook.send(**payload, files=files)