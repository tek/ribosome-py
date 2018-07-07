from typing import Any
import json

from amino import List, Lists

from ribosome.nvim.io.compute import NvimIO
from ribosome.nvim.api.command import nvim_command


def format_json_cmd(args: List[str], data: dict) -> str:
    j = json.dumps(data)
    return f'{args.join_tokens} {j}'


def json_cmd(cmd: str, *args: str, **data: Any) -> NvimIO[str]:
    return nvim_command(cmd, format_json_cmd(Lists.wrap(args), data), verbose=True)


__all__ = ('json_cmd',)
