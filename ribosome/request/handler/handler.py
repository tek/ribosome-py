from typing import Generic, Any, TypeVar, Callable

from amino import List, Lists, Map, _, Boolean, __
from amino.func import flip
from amino.util.string import ToStr, camelcase
from amino.dat import ADT
from amino.boolean import false

from ribosome.request.rpc import RpcHandlerSpec
from ribosome.request.handler.prefix import PrefixStyle, Short
from ribosome.request.handler.method import RpcMethod, CmdMethod, FunctionMethod, AutocmdMethod
from ribosome.nvim.io.compute import NvimIO

A = TypeVar('A')
B = TypeVar('B')
D = TypeVar('D')
P = TypeVar('P')
RHS = TypeVar('RHS', bound=RpcHandlerSpec)
Meth = TypeVar('Meth', bound=RpcMethod)


def program_rpc_options(program: P) -> Map[str, str]:
    return Map(nargs=program.params_spec.nargs.for_vim)


class RequestHandler(Generic[Meth, P], ADT['RequestHandler[Meth, P]']):

    def __init__(
            self,
            method: Meth,
            program: P,
            name: str,
            prefix: PrefixStyle,
            sync: Boolean,
            json: Boolean,
            extra_options: Map[str, Any],
    ) -> None:
        self.method = method
        self.program = program
        self.name = name
        self.prefix = prefix
        self.sync = sync
        self.json = json
        self.extra_options = extra_options

    @staticmethod
    def trans_cmd(prog: P) -> 'RequestHandlerBuilder[CmdMethod]':
        return RequestHandlerBuilder(CmdMethod(), prog)

    @staticmethod
    def trans_function(prog: P) -> 'RequestHandlerBuilder[FunctionMethod]':
        return RequestHandlerBuilder(FunctionMethod(), prog)

    @staticmethod
    def trans_autocmd(prog: P) -> 'RequestHandlerBuilder[AutocmdMethod]':
        return RequestHandlerBuilder(AutocmdMethod(), prog)

    @property
    def options(self) -> Map[str, Any]:
        return self.extra_options ** Map(sync=self.sync) ** program_rpc_options(self.program)

    @property
    def method_str(self) -> str:
        return f'{self.method.method}:{self.name}'

    def vim_cmd_name(self, name: str, prefix: str) -> str:
        pre = name if self.prefix.full else prefix if self.prefix.short else ''
        return f'{camelcase(pre)}{camelcase(self.name)}'


class RequestHandlerBuilder(Generic[Meth]):

    def __init__(self, method: Meth, program: P) -> None:
        self.method = method
        self.program = program

    @property
    def sync_default(self) -> Boolean:
        return Boolean.isinstance(self.method, FunctionMethod)

    def __call__(
            self,
            name: str=None,
            prefix: PrefixStyle=Short(),
            sync: Boolean=None,
            json: Boolean=false,
            **options: Any,
    ) -> RequestHandler:
        name1 = name or self.program.name
        sync1 = self.sync_default if sync is None else sync
        return RequestHandler(
            self.method,
            self.program,
            name1,
            prefix,
            sync1,
            json,
            Map(options),
        )


class RequestHandlers(ToStr):

    @staticmethod
    def cons(*handlers: RequestHandler) -> 'RequestHandlers':
        return RequestHandlers(Map(Lists.wrap(handlers).apzip(_.name).map2(flip)))

    def __init__(self, handlers: Map[str, RequestHandler]) -> None:
        self.handlers = handlers

    def _arg_desc(self) -> List[str]:
        return List(str(self.handlers))

    def rpc_specs(self, name: str, prefix: str) -> List[RpcHandlerSpec]:
        return self.handlers.v / __.spec(name, prefix)


class rpc:

    def __new__(self, prog: P) -> RequestHandlerBuilder[CmdMethod]:
        return RequestHandlerBuilder(CmdMethod(), prog)

    @staticmethod
    def simple(f: Callable[..., NvimIO[A]]) -> RequestHandlerBuilder[CmdMethod]:
        ...



__all__ = ('RequestHandler', 'RequestHandlers')
