from asyncio import sleep as asyncio_sleep
from time import time
from typing import cast

from ircrobots import Bot as BaseBot

from . import Server


async def cron(bot: BaseBot):
    while True:
        # every ten seconds on the ten seconds
        await asyncio_sleep(10 - (time() % 10))

        servers = list(bot.servers.values())
        if servers:
            server = cast(Server, servers[0])
            await server.every_ten_seconds()
