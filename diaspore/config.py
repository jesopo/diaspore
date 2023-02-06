from dataclasses import dataclass
from os.path import expanduser
from typing import List, Optional, Tuple

import yaml


@dataclass
class Config(object):
    server: str
    nickname: str
    username: str
    realname: str
    password: Optional[str]
    channel: str
    ignore: List[str]

    sasl: Tuple[str, str]
    oper: Tuple[str, str]
    client_keypair: Optional[Tuple[str, str]]


def load(filepath: str):
    with open(filepath) as file:
        config_yaml = yaml.safe_load(file.read())

    nickname = config_yaml["nickname"]

    oper_name = config_yaml["oper"]["name"]
    oper_pass = config_yaml["oper"]["pass"]

    tls_keypair: Optional[Tuple[str, str]] = None
    if "tls-keypair" in config_yaml:
        tls_keypair = (
            expanduser(config_yaml["tls-keypair"]["cert"]),
            expanduser(config_yaml["tls-keypair"]["key"]),
        )

    return Config(
        config_yaml["server"],
        nickname,
        config_yaml.get("username", nickname),
        config_yaml.get("realname", nickname),
        config_yaml.get("password", None),
        config_yaml["channel"],
        config_yaml.get("ignore", []),
        (config_yaml["sasl"]["username"], config_yaml["sasl"]["password"]),
        (oper_name, oper_pass),
        tls_keypair,
    )
