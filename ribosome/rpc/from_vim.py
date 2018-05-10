from typing import Any

from amino import do, Do, IO, List

from amino.logging import module_log

from ribosome.rpc.comm import Comm, Exec
from ribosome.rpc.to_vim import handle_response, RpcResponse
from ribosome.rpc.nvim_api import RiboNvimApi
from ribosome.rpc.data.rpc import Rpc
from ribosome.nvim.io.data import NFatal, NResult
from ribosome.rpc.response import validate_rpc_result, report_error

log = module_log()


# TODO fetch nvim api ctor from `Comm`
@do(IO[NResult[List[Any]]])
def execute_rpc(comm: Comm, rpc: Rpc, execute: Exec, plugin_name: str) -> Do:
    thunk = yield IO.delay(execute, rpc.method, rpc.args)
    yield IO.delay(thunk.run_a, RiboNvimApi(plugin_name, comm))


@do(IO[RpcResponse])
def execute_rpc_safe(comm: Comm, rpc: Rpc, execute: Exec, plugin_name: str) -> Do:
    result = yield execute_rpc(comm, rpc, execute, plugin_name).recover(NFatal)
    validated = validate_rpc_result(rpc)(result)
    yield report_error.match(validated)
    return validated


@do(IO[Any])
def execute_rpc_from_vim(rpc: Rpc, comm: Comm, execute: Exec, plugin_name: str) -> Do:
    result = yield execute_rpc_safe(comm, rpc, execute, plugin_name)
    yield handle_response.match(result).run(comm)


__all__ = ('execute_rpc_from_vim')
