from concurrent.futures import Future
from typing import Any

from amino import do, Do, IO
from amino.case import Case

from ribosome.rpc.comm import Comm, RpcType, BlockingRpc, Exec, NonblockingRpc, Rpc, Requests
from ribosome.rpc.api import RiboNvimApi
from ribosome import ribo_log


def exclusive_unregister_callback(comm: Comm, id: int) -> Future:
    with comm.lock:
        return comm.concurrency.requests.from_vim.pop(id)


@do(IO[Future])
def register_request(requests: Requests, id: int) -> Do:
    f = Future()
    yield IO.delay(requests.from_vim.update, id=f)
    return f


@do(IO[None])
def push_request_result(comm: Comm, result: Any, id: int) -> Do:
    f = yield IO.delay(exclusive_unregister_callback, comm, id)
    yield IO.delay(f.set_result, result)


@do(IO[Any])
def exec_rpc(comm: Comm, rpc: Rpc, execute: Exec) -> Do:
    thunk = yield IO.delay(execute, rpc.method, rpc.args, rpc.sync)
    result = yield IO.delay(thunk.run_a, RiboNvimApi('uv', comm))
    yield IO.from_either(result.to_either)


class execute_rpc(Case[RpcType, IO[Any]], alg=RpcType):

    def __init__(self, rpc: Rpc, comm: Comm, execute: Exec) -> None:
        self.rpc = rpc
        self.comm = comm
        self.execute = execute

    @do(IO[Any])
    def blocking_rpc(self, rpc_type: BlockingRpc) -> Do:
        yield self.comm.concurrency.exclusive(register_request, self.comm.concurrency.requests, rpc_type.id)
        result = yield exec_rpc(self.comm, self.rpc, self.execute)
        yield push_request_result(self.comm, result, rpc_type.id)

    def nonblocking_rpc(self, rpc_type: NonblockingRpc) -> IO[Any]:
        return exec_rpc(self.comm, self.rpc, self.execute)


__all__ = ('execute_rpc')
