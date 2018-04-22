from concurrent.futures import Future
from typing import Any, Callable

from amino import do, Either, Do, Try, List

from ribosome.rpc.comm import Comm
from ribosome.rpc.api import RiboNvimApi


def exclusive_unregister_callback(comm: Comm, id: int) -> Future:
    with comm.lock:
        return comm.concurrency.requests.from_vim.pop(id)


@do(Either[str, None])
def push_request_result(comm: Comm, result: Any, id: int) -> Do:
    f = yield Try(exclusive_unregister_callback, comm, id)
    yield Try(f.set_result, result)


@do(Either[str, None])
def execute_request(comm: Comm, id: int, method: str, args: List[Any], sync: bool,
                    execute: Callable[[str, List[Any], bool], Either[str, Any]]) -> Do:
    result = yield execute(method, args, sync).run_a(RiboNvimApi('uv', comm)).to_either
    yield push_request_result(comm, result, id)


__all__ = ('execute_request',)
