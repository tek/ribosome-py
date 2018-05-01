from typing import Any, Tuple

from amino import List, do, Either, Do, Left
from amino.logging import module_log

from ribosome import NvimApi
from ribosome.rpc.comm import Comm, Rpc
from ribosome.rpc.handle import send_request, send_notification

log = module_log()
request_timeout = 10.


# FIXME remove request_timeout
class RiboNvimApi(NvimApi):

    def __init__(self, name: str, comm: Comm) -> None:
        self.name = name
        self.comm = comm

    @do(Either[str, Tuple[NvimApi, Any]])
    def request(self, method: str, args: List[Any], sync: bool) -> Do:
        sender = send_request if sync else send_notification
        rpc_desc = 'request' if sync else 'notification'
        try:
            log.debug(f'api: {rpc_desc} `{method}({args.join_tokens})`')
            comm, result = yield sender(Rpc.nonblocking(method, args), request_timeout).run(self.comm)
            return self.copy(comm=comm), result
        except Exception as e:
            yield Left(f'request error: {e}')


__all__ = ('RiboNvimApi',)
