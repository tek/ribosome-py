from threading import Thread
from queue import Queue
from typing import Any

import msgpack

from kallikrein import k, Expectation
from kallikrein.matchers import contain
from kallikrein.matchers.either import be_right

from amino import List, do, Do, Path, IO, Dat, Map
from amino.test import temp_file
from amino.test.spec import SpecBase
from amino.logging import module_log

from ribosome.nvim.io.compute import NvimIO
from ribosome.nvim.api.variable import variable_set, variable_raw
from ribosome.nvim.api.command import nvim_command
from ribosome.nvim.io.data import NSuccess
from ribosome.nvim.api.rpc import channel_id
from ribosome.nvim.api.function import nvim_call_function
from ribosome.nvim.io.api import N
from ribosome.rpc.uv.uv import Uv, cons_uv_embed
from ribosome.rpc.comm import Comm, RpcComm
from ribosome.config.config import Config
from ribosome.rpc.strict import StrictRpc
from ribosome.rpc.start import start_comm
from ribosome.rpc.handle import comm_request_handler
from ribosome.rpc.api import RiboNvimApi

log = module_log()


def stop(p: Uv) -> None:
    p.loop.stop()


def main_loop(uv: Uv) -> None:
    try:
        uv.loop.run()
    except Exception as e:
        log.error(e)


value = 'successfully set variable'


@do(NvimIO[None])
def run2() -> Do:
    channel = yield channel_id()
    yield variable_set('foo', value)
    v = yield variable_raw('foo')
    yield N.recover_failure(nvim_call_function('rpcrequest', channel, 'meth', sync=True), lambda a: N.pure('failed'))
    return v


@do(NvimIO[None])
def run1() -> Do:
    v = yield run2()
    yield nvim_command('quit')
    return v


def embed_nvim(log: Path) -> Uv:
    embed_nvim_cmdline = List('nvim', f'-V{log}', '-n', '-u', 'NONE', '--embed')
    return cons_uv_embed(embed_nvim_cmdline)


# @do(NvimIO[Callable[[str, List[Any], bool], NvimIO[Any]]])
# def cons_request_handler(config: Config) -> Do:
#     holder = yield prepare_plugin(config)
#     return handler


responses: Map[str, Any] = Map(
    nvim_get_api_info=(1, {}),
)


# TODO incoming rpc methods must have format '{read,write}:{sync,async}:<name>'
# write requests are exclusive and their results update the state.
# sync requests produce responses to vim
# is sync necessary? can also just correspond to the rpc type
# also, read/write should probably just be attrs of the handler
class SessionSpec(SpecBase):
    '''
    test $test
    strict $strict
    '''

    def test(self) -> Expectation:
        log = temp_file('log', 'uv')
        uv, rpc_comm = embed_nvim(log)
        comm = Comm.cons(comm_request_handler, rpc_comm)
        start_comm(comm, Config.cons('uv')).attempt.get_or_raise()
        main = Thread(target=main_loop, args=(uv,))
        main.start()
        api = RiboNvimApi('uv', comm)
        s, r = run1().run(api)
        stop(uv)
        main.join()
        return k(r).must(contain(be_right(value)))

    def strict(self) -> Expectation:
        strict_rpc = StrictRpc.cons(responses)
        rpc_comm = RpcComm(strict_rpc.start_processing, strict_rpc.send, strict_rpc.stop)
        comm = Comm.cons(comm_request_handler, rpc_comm)
        start_comm(comm, Config.cons('uv')).attempt.get_or_raise()
        api = RiboNvimApi('uv', comm)
        s, r = run1().run(api)
        if not isinstance(r, NSuccess):
            print(r)
        strict_rpc.stop()
        return k(1) == 1


__all__ = ('SessionSpec',)
