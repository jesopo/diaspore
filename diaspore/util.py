import traceback
from typing import List, Tuple
from ircrobots import Server
from irctokens import build

from ircchallenge import Challenge
from ircrobots.matching import ANY, Response, SELF
from ircstates.numerics import RPL_RSACHALLENGE2, RPL_ENDOFRSACHALLENGE2


async def oper_up(server: Server, oper_name: str, oper_file: str, oper_pass: str):

    try:
        challenge = Challenge(keyfile=oper_file, password=oper_pass)
    except Exception:
        traceback.print_exc()
    else:
        await server.send(build("CHALLENGE", [oper_name]))
        challenge_text = Response(RPL_RSACHALLENGE2, [SELF, ANY])
        challenge_stop = Response(RPL_ENDOFRSACHALLENGE2, [SELF])
        #:lithium.libera.chat 740 sandcat :foobarbazmeow
        #:lithium.libera.chat 741 sandcat :End of CHALLENGE

        while True:
            challenge_line = await server.wait_for({challenge_text, challenge_stop})
            if challenge_line.command == RPL_RSACHALLENGE2:
                challenge.push(challenge_line.params[1])
            else:
                retort = challenge.finalise()
                await server.send(build("CHALLENGE", [f"+{retort}"]))
                break


# not in ircstates yet
RPL_LINKS = "364"
RPL_ENDOFLINKS = "365"


async def read_links(server: Server) -> List[Tuple[str, int]]:
    links: List[Tuple[str, int]] = []
    async with server.read_lock:
        await server.send(build("LINKS"))
        while True:
            links_line = await server.wait_for(
                {Response(RPL_LINKS, [SELF, ANY, ANY, ANY]), Response(RPL_ENDOFLINKS)}
            )

            if links_line.command == RPL_LINKS:
                server_name = links_line.params[1]
                server_hops = int(links_line.params[3].split(" ", 1)[0])
                links.append((server_name, server_hops))
            else:
                break
    return links
