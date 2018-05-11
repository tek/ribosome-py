from ribosome.nvim.api.util import nvimio_repeat_timeout
from ribosome.nvim.io.compute import NvimIO
from ribosome.nvim.api.rpc import plugin_name
from ribosome.nvim.api.function import nvim_call_json

from amino import do, List, Do
from amino.util.string import camelcase


@do(NvimIO[List[str]])
def program_log() -> Do:
    name = yield plugin_name()
    yield nvim_call_json(f'{camelcase(name)}ProgramLog')


def seen_program(name: str, timeout: float=1., interval=.25) -> NvimIO[None]:
    return nvimio_repeat_timeout(
        program_log,
        lambda a: a.contains(name),
        f'program `{name}` wasn\'t executed',
        timeout=timeout,
        interval=interval,
    )


__all__ = ('program_log', 'seen_program',)
