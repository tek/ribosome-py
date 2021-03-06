from typing import Any, TypeVar, Callable, Generic

from amino import List, Dat, Maybe, Map

from ribosome.nvim.io.compute import NvimIO
from ribosome.compute.program import Program
from ribosome.rpc.data.prefix_style import PrefixStyle, Short, Plain
from ribosome.rpc.data.rpc_method import RpcMethod, CommandMethod, FunctionMethod, AutocmdMethod
from ribosome.util.doc.data import DocBlock

A = TypeVar('A')
default_methods = List(FunctionMethod(), CommandMethod.cons())


class RpcOptions(Dat['RpcOptions']):

    @staticmethod
    def cons(
            name: str=None,
            methods: List[RpcMethod]=default_methods,
            prefix: PrefixStyle=Short(),
            json: bool=False,
            write: bool=True,
            help: DocBlock=None,
            params_help: List[str]=None,
            json_help: Map[str, str]=None,
    ) -> 'RpcOptions':
        return RpcOptions(
            Maybe.optional(name),
            methods,
            prefix,
            json,
            write,
            help or DocBlock.empty(),
            Maybe.optional(params_help),
            Maybe.optional(json_help),
        )


    def __init__(
            self,
            name: Maybe[str],
            methods: List[RpcMethod],
            prefix: PrefixStyle,
            json: bool,
            write: bool,
            help: DocBlock,
            params_help: Maybe[List[str]],
            json_help: Maybe[Map[str, str]],
    ) -> None:
        self.name = name
        self.methods = methods
        self.prefix = prefix
        self.json = json
        self.write = write
        self.help = help
        self.params_help = params_help
        self.json_help = json_help


class RpcProgram(Generic[A], Dat['RpcProgram[A]']):

    @staticmethod
    def cons(program: Program[A], options: RpcOptions=None) -> 'RpcProgram':
        return RpcProgram(program, options or RpcOptions.cons())

    def __init__(self, program: Program[A], options: RpcOptions) -> None:
        self.program = program
        self.options = options

    def conf(self, **kw: Any) -> 'RpcProgram':
        return self.set.options(self.options.copy(**kw))

    @property
    def program_name(self) -> str:
        return self.program.name

    @property
    def rpc_name(self) -> str:
        return self.options.name | self.program_name


class RpcApi:

    def simple(self, f: Callable[..., NvimIO[A]]) -> RpcProgram[A]:
        ...

    def write(self, program: Program[A]) -> RpcProgram[A]:
        return RpcProgram.cons(program)

    def read(self, program: Program[A]) -> RpcProgram[A]:
        return RpcProgram.cons(program, RpcOptions.cons(write=False))

    def autocmd(self, program: Program[A], pattern: str=None, sync: bool=False) -> RpcProgram[A]:
        method = AutocmdMethod.cons(pattern, sync)
        return RpcProgram.cons(program, RpcOptions.cons(methods=List(method))).conf(prefix=Plain())


rpc = RpcApi()


__all__ = ('RpcOptions', 'RpcProgram', 'rpc',)
