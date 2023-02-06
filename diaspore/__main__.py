import asyncio
from argparse import ArgumentParser

from ircrobots import ConnectionParams, SASLUserPass

from . import Bot
from .config import Config, load as config_load
from .cron import cron


async def main(config: Config):
    bot = Bot(config)

    sasl_user, sasl_pass = config.sasl

    params = ConnectionParams.from_hoststring(config.nickname, config.server)
    params.username = config.username
    params.realname = config.realname
    params.password = config.password
    params.sasl = SASLUserPass(sasl_user, sasl_pass)
    params.autojoin = [config.channel]

    if params.tls is not None:
        params.tls.client_keypair = config.client_keypair

    await bot.add_server("irc", params)
    await asyncio.gather(cron(bot), bot.run())


if __name__ == "__main__":
    parser = ArgumentParser()
    parser.add_argument("config")
    args = parser.parse_args()

    config = config_load(args.config)
    asyncio.run(main(config))
