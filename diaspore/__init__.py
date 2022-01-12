from dataclasses import dataclass
from datetime import datetime
from operator import attrgetter
from re import compile as re_compile
from typing import List, Optional

from irctokens import build, Line
from ircrobots import Bot as BaseBot
from ircrobots import Server as BaseServer
from ircstates.numerics import RPL_WELCOME, RPL_YOUREOPER

from .config import Config
from .util import oper_up, read_links

RE_NETSPLIT = re_compile(r"^\*{3} Notice -- Netsplit (?P<near>\S+) <-> (?P<far>\S+) ")
RE_NETJOIN = re_compile(r"^\*{3} Notice -- Netjoin (?P<near>\S+) <-> (?P<far>\S+) ")


@dataclass
class ServerDetails:
    name: str
    hops: int
    seen: Optional[datetime] = None
    pings: int = 0


class Server(BaseServer):
    def __init__(self, bot: BaseBot, name: str, config: Config):
        super().__init__(bot, name)

        self._config = config
        self._links: List[ServerDetails] = []
        self._has_links = False

    def set_throttle(self, rate: int, time: float):
        # turn off throttling
        pass

    async def _log(self, text: str):
        await self.send(build("PRIVMSG", [self._config.channel, text]))

    async def _send_pings(self):
        for i, server in enumerate(self._links):
            await self.send(build("TIME", [server.name]))
            server.pings += 1

            if server.pings == 3:
                await self._log(f"WARN: {server.name} failed to check in twice")

    async def every_ten_seconds(self):
        # this might hit before we've read /links
        if self._has_links:
            await self._send_pings()

    def _server_index(self, server_name: str) -> int:
        for i, server in enumerate(self._links):
            if server.name == server_name:
                return i
        else:
            raise ValueError(f"unknown server name {server_name}")

    async def _read_links(self):
        links: List[ServerDetails] = []
        for server_name, server_hops in await read_links(self):
            links.append(ServerDetails(server_name, server_hops))
        self._links = links

    async def line_read(self, line: Line):
        if line.command == RPL_WELCOME:
            await self.send(build("MODE", [self.nickname, "+g"]))
            oper_name, oper_file, oper_pass = self._config.oper
            await oper_up(self, oper_name, oper_file, oper_pass)

        elif line.command == RPL_YOUREOPER:
            # s - netsplit snotes
            await self.send(build("MODE", [self.nickname, "-s+s", "+s"]))
            await self._read_links()
            self._has_links = True

        elif line.command == "391" and line.source is not None:
            # RPL_TIME
            server_name = line.source
            server = self._links[self._server_index(server_name)]

            server.pings -= 1
            server.seen = datetime.utcnow()

            if server.pings == 1:
                await self._log(f"INFO: {server.name} caught up")

        elif (
            line.command == "NOTICE"
            and line.params[0] == "*"
            and line.source is not None
            and not "!" in line.source
        ):

            # snote!

            message = line.params[1]

            if (p_netsplit := RE_NETSPLIT.search(message)) is not None:
                near_name = p_netsplit.group("near")
                far_name = p_netsplit.group("far")

                near = self._links[self._server_index(near_name)]
                self._links.append(ServerDetails(far_name, near.hops + 1))
                self._links.sort(key=attrgetter("hops", "name"))

            elif (p_netjoin := RE_NETJOIN.search(message)) is not None:
                near_name = p_netjoin.group("near")
                far_name = p_netjoin.group("far")

                self._links.pop(self._server_index(far_name))

    def line_preread(self, line: Line):
        print(f"< {line.format()}")

    def line_presend(self, line: Line):
        print(f"> {line.format()}")


class Bot(BaseBot):
    def __init__(self, config: Config):
        super().__init__()
        self._config = config

    def create_server(self, name: str):
        return Server(self, name, self._config)
