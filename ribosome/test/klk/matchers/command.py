from amino import do, Do

from ribosome.nvim.io.compute import NvimIO
from ribosome.nvim.api.exists import command_exists, command_exists_not

from kallikrein import Expectation, k


@do(NvimIO[Expectation])
def command_must_exist(name: str) -> Do:
    exists = yield command_exists(name)
    return k(exists).true


@do(NvimIO[Expectation])
def command_must_not_exist(name: str) -> Do:
    exists_not = yield command_exists_not(name)
    return k(exists_not).true


__all__ = ('command_must_exist', 'command_must_not_exist',)
