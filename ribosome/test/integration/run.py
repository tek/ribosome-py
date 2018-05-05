from typing import Callable, Tuple, Any, TypeVar, Generic

from amino import Lists, Map, List, __, Either, Left, Right, do, Do, Nil

from kallikrein.expectable import Expectable
from amino.dat import Dat
from amino.lenses.lens import lens
from amino.logging import module_log

from ribosome.nvim.io.state import NS
from ribosome.config.config import Config
from ribosome.config.component import ComponentData
from ribosome.nvim.api.data import NvimApi, StrictNvimApi
from ribosome.nvim.io.compute import NvimIO
from ribosome.data.plugin_state import PluginState
from ribosome.nvim.api.variable import variable_set
from ribosome.nvim.io.api import N
from ribosome.compute.program import Program
from ribosome.config.resources import Resources
from ribosome.compute.output import ProgOutput
from ribosome.compute.prog import Prog
from ribosome.test.klk.expectable import kn
from ribosome.nvim.io.data import NResult
from ribosome.rpc.state import cons_state
from ribosome.components.internal.update import update_components
from ribosome.rpc.comm import StateGuard
from ribosome.rpc.to_plugin import run_programs, run_program
from ribosome.rpc.data.rpc import RpcArgs

log = module_log()
A = TypeVar('A')
B = TypeVar('B')
C = TypeVar('C')
D = TypeVar('D')
CC = TypeVar('CC')
DIO = TypeVar('DIO')
R = TypeVar('R')
ProgInt = Callable[[ProgOutput], Callable[[R], Prog[B]]]
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


class RequestHelperBuilder(Generic[D, CC], Dat['RequestHelperBuilder[D, CC]']):

    def __init__(
            self,
            config: Config[D, CC],
            comps: List[str],
            vars: Map[str, Any]=Map(),
            io_interpreter: ProgInt=None,
            logger: Program[None]=None,
    ) -> None:
        self.config = config
        self.comps = comps
        self.vars = vars
        self.io_interpreter = io_interpreter
        self.logger = logger

    def create(self, cons_vim: Callable[[dict], NvimApi]) -> 'RequestHelper[D, CC]':
        comps_var = Map({f'{self.config.basic.name}_components': self.comps})
        vim = cons_vim(self.vars ** comps_var)
        state0 = cons_state(self.config, self.io_interpreter, self.logger)
        state = update_components(Right(self.comps)).run_s(state0).get_or_raise()
        return RequestHelper(vim, self.config, state)

    def nvim(self, vim: NvimApi) -> 'RequestHelper[D, CC]':
        def cons_vim(vars: dict) -> NvimApi:
            for k, v in vars.items():
                variable_set(k, v).unsafe(vim)
            return vim
        return self.create(cons_vim)

    def strict(
            self,
            request_handler: Handler=no_handler,
            function_handler: Handler=no_handler,
            command_handler: Handler=no_handler,
    ) -> 'RequestHelper[D, CC]':
        def cons_vim(vars: Map[str, Any]) -> StrictNvimApi:
            handler = StrictRequestHandler(request_handler, function_handler, command_handler)
            return StrictNvimApi(self.config.basic.name, vars, handler, Nil)
        return self.create(cons_vim)


class RequestHelper(Generic[D, CC], Dat['RequestHelper[D, CC]']):

    @staticmethod
    def nvim(config: Config[D, CC], vim: NvimApi, *comps: str, **kw: Any) -> 'RequestHelper[D, CC]':
        return RequestHelper.cons(config, *comps, **kw).nvim(vim)

    @staticmethod
    def strict(
            config: Config,
            *comps: str,
            request_handler: Handler=no_handler,
            **kw: Any,
    ) -> 'RequestHelper':
        return RequestHelper.cons(config, *comps, **kw).strict(request_handler)

    @staticmethod
    def cons(config: Config[D, CC], *comps: str, **kw: Any) -> RequestHelperBuilder[D, CC]:
        return RequestHelperBuilder(config, Lists.wrap(comps), **kw)

    def __init__(self, vim: NvimApi, config: Config, state: PluginState[D, CC]) -> None:
        self.vim = vim
        self.config = config
        self.state = state

    @property
    def guard(self) -> StateGuard[D]:
        return StateGuard.cons(self.state)

    def resolve_program(self, name: str) -> List[Program]:
        return self.guard.state.program_by_name(name)

    def run_programs(self, name: str, args: tuple=()) -> NS[PluginState[D, CC], Any]:
        programs = self.guard.state.programs_by_name(name)
        return run_programs(programs, RpcArgs.cons(Lists.wrap(args)))

    def run(self, name: str, args=(), warn_error: bool=True) -> NvimIO[Tuple[PluginState, Any]]:
        program = self.resolve_program(name).get_or_raise()
        def check_error(result: NResult) -> NvimIO[None]:
            if warn_error:
                log.error(f'NvimIO failed: {result}')
            return N.unit
        io = run_program(program, RpcArgs.cons(Lists.wrap(args))).run(self.state)
        return N.ensure_failure(io, check_error)

    def run_s(self, name: str, args=(), warn_error: bool=True) -> NvimIO[PluginState]:
        return self.run(name, args).map2(lambda s, a: s)

    def run_a(self, name: str, args=(), warn_error: bool=True) -> NvimIO[Any]:
        return self.run(name, args).map2(lambda s, a: a)

    def unsafe_run(self, name: str, args=(), warn_error: bool=True) -> Tuple[PluginState, Any]:
        return self.run(name, args=args).unsafe(self.vim)

    def unsafe_run_s(self, name: str, args=(), warn_error: bool=True) -> PluginState:
        return self.run_s(name, args=args).unsafe(self.vim)

    def unsafe_run_a(self, name: str, args=(), warn_error: bool=True) -> Any:
        return self.run_a(name, args=args).unsafe(self.vim)

    def update_data(self, **kw: Any) -> 'RequestHelper[D, CC]':
        return lens.state.data.modify(__.copy(**kw))(self)

    def update_component(self, name: str, **kw: Any) -> 'RequestHelper[D, CC]':
        return self.mod.state(__.modify_component_data(name, __.copy(**kw)))

    def component_res(self, data: C) -> Resources[C, CC]:
        return self.state.resources_with(ComponentData(self.state.data, data))

    def component_res_for(self, name: str) -> Resources[C, CC]:
        data = self.state.data_by_name(name).get_or_raise()
        return self.state.resources_with(ComponentData(self.state.data, data))

    def k(self, f: Callable[..., NvimIO[A]], *a: Any, **kw: Any) -> Expectable:
        return kn(self.vim, f, *a, **kw)

    def k_s(self, prog: str, *a: Any, **kw: Any) -> Expectable:
        return self.k(self.run_s, prog, a, **kw)


def request_helper(
        config: Config[D, CC],
        *comps: str,
        vars: Map[str, Any]=Map(),
        io_interpreter: ProgInt=None,
) -> NvimIO[RequestHelper[D, CC]]:
    return N.delay(lambda v: RequestHelper.nvim(config, v, *comps, vars=vars, io_interpreter=io_interpreter))


__all__ = ('RequestHelper', 'request_helper')
