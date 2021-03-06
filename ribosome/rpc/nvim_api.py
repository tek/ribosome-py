from typing import Any, Tuple

from amino import List, do, Either, Do, Left
from amino.logging import module_log

from ribosome import NvimApi
from ribosome.rpc.comm import Comm
from ribosome.rpc.to_vim import send_request, send_notification
from ribosome.rpc.data.rpc import Rpc

log = module_log()


class RiboNvimApi(NvimApi):

    def __init__(self, name: str, comm: Comm) -> None:
        self.name = name
        self.comm = comm

    @do(Either[str, Tuple[NvimApi, Any]])
    def request(self, method: str, args: List[Any], sync: bool, timeout: float) -> Do:
        sender = send_request if sync else send_notification
        rpc_desc = 'request' if sync else 'notification'
        try:
            log.debug1(lambda: f'api: {rpc_desc} `{method}({args.join_tokens})`')
            a = sender(Rpc.nonblocking(method, args), timeout)
            comm, result = yield a.run(self.comm).attempt
            return self.copy(comm=comm), result
        except Exception as e:
            yield Left(f'request error: {e}')


__all__ = ('RiboNvimApi',)
