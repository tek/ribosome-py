from typing import Generic, Any, TypeVar, Callable

from amino import List, Lists, Map, _, Boolean, __, Dat, Maybe
from amino.func import flip
from amino.util.string import camelcase
from amino.dat import ADT
from amino.boolean import false

from ribosome.request.rpc import RpcHandlerSpec
from ribosome.request.handler.prefix import PrefixStyle, Short
from ribosome.request.handler.method import RpcMethod, CommandMethod, FunctionMethod, AutocmdMethod
from ribosome.nvim.io.compute import NvimIO
from ribosome.compute.program import Program

A = TypeVar('A')
B = TypeVar('B')
D = TypeVar('D')
RHS = TypeVar('RHS', bound=RpcHandlerSpec)
Meth = TypeVar('Meth', bound=RpcMethod)


def program_rpc_options(program: Program) -> Map[str, str]:
    return Map(nargs=program.params_spec.nargs.for_vim)


class RequestHandler(Generic[Meth], ADT['RequestHandler[Meth]']):

    def __init__(
            self,
            method: Meth,
            program: Program,
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
    def trans_cmd(prog: Program) -> 'RequestHandlerBuilder[CommandMethod]':
        return RequestHandlerBuilder(CommandMethod.cons(), prog)

    @staticmethod
    def trans_function(prog: Program) -> 'RequestHandlerBuilder[FunctionMethod]':
        return RequestHandlerBuilder(FunctionMethod(), prog)

    @staticmethod
    def trans_autocmd(prog: Program) -> 'RequestHandlerBuilder[AutocmdMethod]':
        return RequestHandlerBuilder(AutocmdMethod.cons(), prog)

    @property
    def options(self) -> Map[str, Any]:
        return self.extra_options ** Map(sync=self.sync) ** program_rpc_options(self.program)

    def vim_cmd_name(self, name: str, prefix: str) -> str:
        pre = name if self.prefix.full else prefix if self.prefix.short else ''
        return f'{camelcase(pre)}{camelcase(self.name)}'


class RequestHandlerBuilder(Generic[Meth]):

    def __init__(self, method: Meth, program: Program) -> None:
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


class RequestHandlers(Dat['RequestHandlers']):

    @staticmethod
    def cons(*handlers: RequestHandler) -> 'RequestHandlers':
        return RequestHandlers(Map(Lists.wrap(handlers).apzip(_.name).map2(flip)))

    def __init__(self, handlers: Map[str, RequestHandler]) -> None:
        self.handlers = handlers

    def rpc_specs(self, name: str, prefix: str) -> List[RpcHandlerSpec]:
        return self.handlers.v / __.spec(name, prefix)


default_methods = List(FunctionMethod(), CommandMethod.cons())


class RpcOptions(Dat['RpcOptions']):

    @staticmethod
    def cons(
            name: str=None,
            methods: List[RpcMethod]=default_methods,
            prefix: PrefixStyle=Short(),
            json: bool=False,
            write: bool=True,
    ) -> 'RpcOptions':
        return RpcOptions(Maybe.optional(name), methods, prefix, json, write)


    def __init__(
            self,
            name: Maybe[str],
            methods: List[RpcMethod],
            prefix: PrefixStyle,
            json: bool,
            write: bool,
    ) -> None:
        self.name = name
        self.methods = methods
        self.prefix = prefix
        self.json = json
        self.write = write


class RpcProgram(Dat['RpcProgram']):

    @staticmethod
    def cons(program: Program, options: RpcOptions=None) -> 'RpcProgram':
        return RpcProgram(program, options or RpcOptions.cons())

    def __init__(self, program: Program, options: RpcOptions) -> None:
        self.program = program
        self.options = options

    def conf(self, **kw: Any) -> 'RpcProgram':
        return self.set.options(self.options.copy(**kw))

    @property
    def rpc_name(self) -> str:
        return self.options.name | self.program.name


class RpcArgs(Dat['RpcArgs']):

    def __init__(self, args: List[Any], bang: bool) -> None:
        self.args = args
        self.bang = bang

    @property
    def string(self) -> str:
        return self.args.join_comma


class RpcApi:

    def __call__(self, prog: Program) -> RequestHandlerBuilder[CommandMethod]:
        return RequestHandlerBuilder(CommandMethod(), prog)

    def simple(self, f: Callable[..., NvimIO[A]]) -> RequestHandlerBuilder[CommandMethod]:
        ...

    def write(self, program: Program) -> RpcProgram:
        return RpcProgram.cons(program)

    def autocmd(self, program: Program) -> RpcProgram:
        return RpcProgram.cons(program, RpcOptions.cons(methods=List(AutocmdMethod.cons())))


rpc = RpcApi()


__all__ = ('RpcOptions', 'RpcProgram', 'RpcArgs', 'rpc',)
