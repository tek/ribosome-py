from typing import Any, Callable

from amino import IO, List, ADT
from amino.case import Case
from amino.logging import module_log

from ribosome.rpc.data.rpc_type import RpcType, BlockingRpc, NonblockingRpc
from ribosome.rpc.data.rpc import Rpc
from ribosome.nvim.io.data import NFatal, NResult, NSuccess, NError
from ribosome import ribo_log

log = module_log()


class RpcResponse(ADT['RpcResponse']):
    pass


class RpcSyncError(RpcResponse):

    def __init__(self, error: str, request_id: int) -> None:
        self.error = error
        self.request_id = request_id


class RpcAsyncError(RpcResponse):

    def __init__(self, error: str) -> None:
        self.error = error


class RpcSyncSuccess(RpcResponse):

    def __init__(self, result: Any, request_id: int) -> None:
        self.result = result
        self.request_id = request_id


class RpcAsyncSuccess(RpcResponse):
    pass


def ensure_single_result(rpc: Rpc, tpe: BlockingRpc) -> Callable[[Any, List[Any]], RpcResponse]:
    def ensure_single_result(head: Any, tail: List[Any]) -> RpcResponse:
        return (
            RpcSyncSuccess(head, tpe.id)
            if tail.empty else
            RpcSyncError(f'multiple results for {rpc}', tpe.id)
        )
    return ensure_single_result


def no_result(rpc: Rpc, tpe: BlockingRpc) -> RpcResponse:
    return RpcSyncError(f'no result for {rpc}', tpe.id)


class validate_success_response(Case[RpcType, RpcResponse], alg=RpcType):

    def __init__(self, result: NSuccess[List[Any]], rpc: Rpc) -> None:
        self.result = result
        self.rpc = rpc

    def blocking(self, tpe: BlockingRpc) -> RpcResponse:
        return self.result.value.uncons.map2(ensure_single_result(self.rpc, tpe)).get_or(no_result, self.rpc, tpe)

    def nonblocking(self, tpe: NonblockingRpc) -> RpcResponse:
        return RpcAsyncSuccess()


class error_response(Case[RpcType, RpcResponse], alg=RpcType):

    def __init__(self, error: str) -> None:
        self.error = error

    def blocking(self, tpe: BlockingRpc) -> RpcResponse:
        return RpcSyncError(self.error, tpe.id)

    def nonblocking(self, tpe: NonblockingRpc) -> RpcResponse:
        return RpcAsyncError(self.error)


class validate_rpc_result(Case[NResult[List[Any]], RpcResponse], alg=NResult):

    def __init__(self, rpc: Rpc) -> None:
        self.rpc = rpc

    def success(self, result: NSuccess[List[Any]]) -> RpcResponse:
        return validate_success_response(result, self.rpc)(self.rpc.tpe)

    def error(self, result: NError[List[Any]]) -> RpcResponse:
        return error_response(result.error)(self.rpc.tpe)

    def fatal(self, result: NFatal[List[Any]]) -> RpcResponse:
        log.caught_exception_error(f'executing {self.rpc} from vim', result.exception)
        return error_response(f'fatal error in {self.rpc}')(self.rpc.tpe)


class report_error(Case[RpcResponse, IO[None]], alg=RpcResponse):

    def sync_error(self, response: RpcSyncError) -> IO[None]:
        return IO.delay(log.debug, response.error)

    def async_error(self, response: RpcAsyncError) -> IO[None]:
        return IO.delay(ribo_log.error, response.error)

    def case_default(self, response: RpcResponse) -> IO[None]:
        return IO.pure(None)


__all__ = ('RpcResponse', 'RpcSyncError', 'RpcAsyncError', 'RpcSyncSuccess', 'RpcAsyncSuccess', 'validate_rpc_result',
           'report_error',)
