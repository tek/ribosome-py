from typing import Callable, Optional

from amino import ADT
from amino.logging import module_log

log = module_log()


class RpcReadError(ADT['RpcReadError']):
    pass


class RpcProcessExit(RpcReadError):
    pass


class RpcReadErrorUnknown(RpcReadError):

    def __init__(self, message: str) -> None:
        self.message = message


def processing_error(data: Optional[bytes]) -> Callable[[Exception], None]:
    def processing_error(error: Exception) -> None:
        if data:
            log.debug(f'{error}: {data}')
        log.error(f'error processing message from nvim: {error}')
    return processing_error


__all__ = ('RpcReadError', 'RpcProcessExit', 'RpcReadErrorUnknown', 'processing_error',)
