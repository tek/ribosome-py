from typing import Callable, Tuple, Any

from amino import Map, List, Either, Left, Right, do, Do

from ribosome.nvim.api.data import NvimApi, StrictNvimApi

Handler = Callable[['StrictNvimApi', str, List[Any]], Either[str, Tuple[NvimApi, Any]]]


def api_info(vim: NvimApi, name: str, args: List[Any]) -> Either[str, Tuple[NvimApi, Any]]:
    return Right((vim, (1, {})))


def rh_write(vim: NvimApi, name: str, args: List[Any]) -> Either[str, Tuple[NvimApi, Any]]:
    return Right((vim, None))


@do(Either[str, Tuple[NvimApi, Any]])
def default_request_handler(vim: NvimApi, name: str, args: List[Any]) -> Do:
    handler = yield default_request_handlers.lift(name).to_either(f'no default request handler for {name}')
    yield handler(vim, name, args)


@do(Either[str, Tuple[NvimApi, Any]])
def pop_first(vim: NvimApi, name: str, args: List[Any]) -> Do:
    name1, args1 = yield args.uncons.to_either(f'invalid command: {name}({args})')
    yield default_request_handler(vim, name1, args1)


default_request_handlers = Map({
    'silent': pop_first,
    'silent!': pop_first,
    'nvim_get_api_info': api_info,
    'nvim_command': rh_write,
    'nvim_out_write': rh_write,
    'nvim_call_function': pop_first,
})


@do(Either[str, Tuple[NvimApi, Any]])
def specific_handler(desc: str, handler: Handler, vim: StrictNvimApi, name: str, args: List[Any]) -> Do:
    name1, args1 = yield args.uncons.to_either(f'empty {desc} args: {name}')
    yield handler(vim, name1, args1)


@do(Either[str, Tuple[NvimApi, Any]])
def function_handler(handler: Handler, vim: StrictNvimApi, name: str, args: List[Any]) -> Do:
    yield specific_handler('function call', handler, vim, name, args)


@do(Either[str, Tuple[NvimApi, Any]])
def command_handler(handler: Handler, vim: StrictNvimApi, name: str, args: List[Any]) -> Do:
    yield specific_handler('command', handler, vim, name, args)


class StrictRequestHandler:

    def __init__(
            self,
            extra: Handler,
            function_handler: Handler,
            command_handler: Handler,
    ) -> None:
        self.extra = extra
        self.function_handler = function_handler
        self.command_handler = command_handler

    def __call__(self, vim: NvimApi, name: str, args: List[Any], sync: bool) -> Either[List[str], Tuple[NvimApi, Any]]:
        return (
            self.extra(vim, name, args)
            .lmap(List)
            .accum_error_lift(function_handler, self.function_handler, vim, name, args)
            .accum_error_lift(command_handler, self.command_handler, vim, name, args)
            .accum_error_lift(default_request_handler, vim, name, args)
        )


def no_handler(vim: NvimApi, name: str, args: List[Any]) -> Either[str, Tuple[NvimApi, Any]]:
    return Left(f'no handler for {name}')


__all__ = ('StrictRequestHandler', 'no_handler', 'Handler',)
