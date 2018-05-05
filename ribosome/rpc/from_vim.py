from typing import Any

from amino import do, Do, IO
from amino.case import Case
from amino.logging import module_log

from ribosome.rpc.comm import Comm, Exec
from ribosome.rpc.to_vim import send_response
from ribosome.rpc.nvim_api import RiboNvimApi
from ribosome.rpc.data.rpc_type import RpcType, BlockingRpc, NonblockingRpc
from ribosome.rpc.data.rpc import Rpc

log = module_log()


@do(IO[Any])
def execute_rpc(comm: Comm, rpc: Rpc, execute: Exec) -> Do:
    thunk = yield IO.delay(execute, rpc.method, rpc.args, rpc.sync)
    yield IO.delay(thunk.run_a, RiboNvimApi('uv', comm))


class execute_rpc_from_vim(Case[RpcType, IO[Any]], alg=RpcType):

    def __init__(self, rpc: Rpc, comm: Comm, execute: Exec) -> None:
        self.rpc = rpc
        self.comm = comm
        self.execute = execute

    @do(IO[Any])
    def blocking_rpc(self, rpc_type: BlockingRpc) -> Do:
        result = yield execute_rpc(self.comm, self.rpc, self.execute)
        yield send_response(self.rpc, rpc_type.id, result).run(self.comm)

    def nonblocking_rpc(self, rpc_type: NonblockingRpc) -> IO[Any]:
        return execute_rpc(self.comm, self.rpc, self.execute)


__all__ = ('execute_rpc_from_vim')
