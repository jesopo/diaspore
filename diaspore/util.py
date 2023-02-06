from typing import List, Tuple
from ircrobots import Server
from irctokens import build

from ircrobots.matching import ANY, Response, SELF

# not in ircstates yet
RPL_LINKS = "364"
RPL_ENDOFLINKS = "365"


async def read_links(server: Server) -> List[Tuple[str, str]]:
    links: List[Tuple[str, str]] = []
    async with server.read_lock:
        await server.send(build("LINKS"))
        while True:
            links_line = await server.wait_for(
                {Response(RPL_LINKS, [SELF, ANY, ANY]), Response(RPL_ENDOFLINKS)}
            )

            if links_line.command == RPL_LINKS:
                server_name = links_line.params[1]
                uplink_name = links_line.params[2]
                links.append((server_name, uplink_name))
            else:
                break
    return links
