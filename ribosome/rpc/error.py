from typing import Callable, Optional

from amino import ADT, do, Do, List
from amino.logging import module_log

from ribosome.nvim.io.compute import NvimIO
from ribosome.nvim.api.exists import function_exists
from ribosome.nvim.api.function import define_function

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


stderr_handler_body = '''
let err = substitute(join(a:data, '\\r'), '"', '\\"', 'g')
try
    python3 import amino
    python3 from ribosome.logging import ribosome_envvar_file_logging
    python3 ribosome_envvar_file_logging()
    execute 'python3 amino.amino_log.error(f"""error starting rpc job on channel ' . a:id . ':\\r' . err . '""")'
catch //
    echohl ErrorMsg
    echo err
    echohl None
endtry
'''


def rpc_stderr_handler_name(prefix: str) -> str:
    return f'{prefix}RpcStderr'


@do(NvimIO[str])
def define_rpc_stderr_handler(prefix: str) -> Do:
    name = rpc_stderr_handler_name(prefix)
    exists = yield function_exists(name)
    if not exists:
        yield define_function(name, List('id', 'data', 'event'), stderr_handler_body)
    return name


__all__ = ('RpcReadError', 'RpcProcessExit', 'RpcReadErrorUnknown', 'processing_error', 'define_rpc_stderr_handler',
           'rpc_stderr_handler_name',)
