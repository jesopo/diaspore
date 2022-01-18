from collections import OrderedDict
from dataclasses import dataclass, field
from datetime import datetime
from re import compile as re_compile
from typing import Dict, Optional, Set
from typing import OrderedDict as TOrderedDict

from irctokens import build, Line
from ircrobots import Bot as BaseBot
from ircrobots import Server as BaseServer
from ircstates.numerics import RPL_WELCOME, RPL_YOUREOPER

from .config import Config
from .util import oper_up, read_links

RE_NETSPLIT = re_compile(r"^\*{3} Notice -- Netsplit (?P<near>\S+) <-> (?P<far>\S+) ")
RE_NETJOIN = re_compile(r"^\*{3} Notice -- Netjoin (?P<near>\S+) <-> (?P<far>\S+) ")
RE_CLICONN = re_compile(r"^\*{3} Notice -- Client connecting: (?P<nick>\S+) ")
RE_CLIEXIT = re_compile(r"^\*{3} Notice -- Client exiting: (?P<nick>\S+) ")


@dataclass
class ServerDetails:
    hops: int
    pings: int = 0
    users: int = -1

    last_pong: Optional[datetime] = None
    last_conn: Optional[datetime] = None

    downlinks: Set[str] = field(default_factory=set)


class Server(BaseServer):
    def __init__(self, bot: BaseBot, name: str, config: Config):
        super().__init__(bot, name)

        self._config = config
        self._servers: TOrderedDict[str, ServerDetails] = OrderedDict()
        self._has_links = False

    def set_throttle(self, rate: int, time: float):
        # turn off throttling
        pass

    async def _log(self, text: str):
        await self.send(build("PRIVMSG", [self._config.channel, text]))

    async def _send_pings(self):
        now = datetime.utcnow()
        for server_name, server in self._servers.items():
            if server_name in self._config.ignore:
                continue

            await self.send(build("TIME", [server_name]))

            if server.pings == 2:
                out = f"WARN: {server_name} failed to check in twice"
                if server.last_pong is not None:
                    since = (now - server.last_pong).total_seconds()
                    out += f" (seen {since:.2f}s ago)"
                await self._log(out)
            server.pings += 1

    async def _send_lusers(self):
        for server_name, server in self._servers.items():
            # only LUSERS servers who we've not yet got an LUSERS for
            if server.users == -1:
                await self.send(build("LUSERS", ["*", server_name]))

    async def every_ten_seconds(self):
        # this might hit before we've read /links
        if self._has_links:
            await self._send_pings()

    async def _read_links(self):
        for server_name, uplink_name in await read_links(self):
            if server_name in self._servers:
                # seen this server on a previous /links
                continue
            else:
                uplink = self._servers[uplink_name]
                self._servers[server_name] = ServerDetails(uplink.hops + 1)
                uplink.downlinks.add(server_name)

    async def line_read(self, line: Line):
        if line.command == RPL_WELCOME and line.source is not None:
            self._servers[line.source] = ServerDetails(0)
            await self.send(build("MODE", [self.nickname, "+g"]))
            oper_name, oper_file, oper_pass = self._config.oper
            await oper_up(self, oper_name, oper_file, oper_pass)

        elif line.command == RPL_YOUREOPER:
            # F - remote cliconns
            # c - local cliconns
            # s - netsplit snotes
            await self.send(build("MODE", [self.nickname, "-s+s", "+Fcs"]))
            await self._read_links()
            self._has_links = True
            await self._send_lusers()

        elif line.command == "391" and line.source is not None:
            # RPL_TIME
            server = self._servers[line.source]
            server.pings -= 1
            server.last_pong = datetime.utcnow()

            if server.pings == 1:
                await self._log(f"INFO: {line.source} caught up")

        elif line.command == "265" and line.source is not None and self._has_links:
            # RPL_LOCALUSERS
            server = self._servers[line.source]
            server.users = int(line.params[1])
            server.last_pong = datetime.utcnow()

        elif (
            line.command == "NOTICE"
            and line.params[0] == "*"
            and line.source is not None
            and not "!" in line.source
            and self.registered
        ):

            # snote!

            server = self._servers[line.source]
            message = line.params[1]

            if RE_CLICONN.search(message) and not server.users == -1:
                server.last_conn = datetime.utcnow()
                server.users += 1

            elif RE_CLIEXIT.search(message) and not server.users == -1:
                server.users -= 1

            elif (
                p_netsplit := RE_NETSPLIT.search(message)
            ) is not None and self._has_links:

                near_name = p_netsplit.group("near")
                far_name = p_netsplit.group("far")

                near = self._servers[near_name]
                far = self._servers.pop(far_name)
                near.downlinks.remove(far_name)

                affected: Set[str] = set()
                downlinks = list(far.downlinks)
                while downlinks:
                    downlink_name = downlinks.pop(0)
                    affected.add(downlink_name)

                    downlink = self._servers.pop(downlink_name)
                    downlinks.extend(downlink.downlinks)

                out = f"WARN: {far_name} split from {near_name}"
                if affected:
                    affected_s = ", ".join(sorted(affected))
                    out += f" (took out {affected_s})"
                await self._log(out)

            elif (
                p_netjoin := RE_NETJOIN.search(message)
            ) is not None and self._has_links:

                near_name = p_netjoin.group("near")
                far_name = p_netjoin.group("far")

                await self._read_links()
                await self._send_lusers()

                far = self._servers[far_name]
                far.last_pong = datetime.utcnow()

                await self._log(f"INFO: {far_name} joined to {near_name}")

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
