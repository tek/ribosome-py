from typing import Callable, Tuple, Any, TypeVar, Generic

from amino import Lists, Map, List, __, Either, Left, Right, do, Do, Nil

from kallikrein.expectable import Expectable
from amino.dat import Dat
from amino.lenses.lens import lens

from ribosome.host import init_state
from ribosome.request.execute import request_job, traverse_programs, run_request_handler
from ribosome.nvim.io.state import NS
from ribosome.config.config import Config
from ribosome.config.settings import Settings
from ribosome.config.component import ComponentData
from ribosome.nvim.api.data import NvimApi, StrictNvimApi
from ribosome.nvim.io.compute import NvimIO
from ribosome.data.plugin_state import PluginState
from ribosome.nvim.api.variable import variable_set
from ribosome.nvim.io.api import N
from ribosome.request.job import RequestJob
from ribosome.compute.program import Program
from ribosome.config.resources import Resources
from ribosome.data.plugin_state_holder import PluginStateHolder
from ribosome.compute.output import ProgOutput
from ribosome.compute.prog import Prog
from ribosome.test.klk import kn

A = TypeVar('A')
B = TypeVar('B')
C = TypeVar('C')
D = TypeVar('D')
S = TypeVar('S', bound=Settings)
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
    name1, args1 = yield args.detach_head.to_either(f'invalid command: {name}({args})')
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
    name1, args1 = yield args.detach_head.to_either(f'empty {desc} args: {name}')
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

    def __call__(self, vim: NvimApi, name: str, args: List[Any]) -> Either[List[str], Tuple[NvimApi, Any]]:
        return (
            self.extra(vim, name, args)
            .lmap(List)
            .accum_error_lift(function_handler, self.function_handler, vim, name, args)
            .accum_error_lift(command_handler, self.command_handler, vim, name, args)
            .accum_error_lift(default_request_handler, vim, name, args)
        )


def no_handler(vim: NvimApi, name: str, args: List[Any]) -> Either[str, Tuple[NvimApi, Any]]:
    return Left(f'no handler for {name}')


class RequestHelperBuilder(Generic[S, D, CC], Dat['RequestHelperBuilder[S, D, CC]']):

    def __init__(
            self,
            config: Config[S, D, CC],
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

    def create(self, cons_vim: Callable[[dict], NvimApi]) -> 'RequestHelper[S, D, CC]':
        comps_var = Map({f'{self.config.basic.name}_components': self.comps})
        vim = cons_vim(self.vars ** comps_var)
        vim1, state = init_state(self.config, io_interpreter=self.io_interpreter, logger=self.logger).unsafe_run(vim)
        return RequestHelper(vim, self.config, state)

    def nvim(self, vim: NvimApi) -> 'RequestHelper[S, D, CC]':
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
    ) -> 'RequestHelper[S, D, CC]':
        def cons_vim(vars: Map[str, Any]) -> StrictNvimApi:
            handler = StrictRequestHandler(request_handler, function_handler, command_handler)
            return StrictNvimApi(self.config.basic.name, vars, handler, Nil)
        return self.create(cons_vim)


class RequestHelper(Generic[S, D, CC], Dat['RequestHelper[S, D, CC]']):

    @staticmethod
    def nvim(config: Config[S, D, CC], vim: NvimApi, *comps: str, **kw: Any) -> 'RequestHelper[S, D, CC]':
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
    def cons(config: Config[S, D, CC], *comps: str, **kw: Any) -> RequestHelperBuilder[S, D, CC]:
        return RequestHelperBuilder(config, Lists.wrap(comps), **kw)

    def __init__(self, vim: NvimApi, config: Config, state: PluginState[S, D, CC]) -> None:
        self.vim = vim
        self.config = config
        self.state = state

    @property
    def holder(self) -> PluginStateHolder[D]:
        return PluginStateHolder.strict(self.state)

    @property
    def settings(self) -> S:
        return self.state.basic.settings

    def request_job(self, name: str, args: tuple, sync: bool=True) -> Tuple[RequestJob, List[Program]]:
        job = request_job(self.holder, name, (args,), sync)
        return job, job.state.state.programs.lift(job.name).get_or_fail(f'no matching program for `{job.name}`')

    def traverse_programs(self, name: str, args: tuple=(), sync: bool=True) -> NS[PluginState[S, D, CC], Any]:
        job, program = self.request_job(name, args, sync)
        return traverse_programs(program, Lists.wrap(args))

    def run(self, name: str, args=(), sync: bool=True) -> NvimIO[Tuple[PluginState, Any]]:
        job, programs = self.request_job(name, args, sync)
        program = programs.head.get_or_fail('multiple programs')
        return (
            run_request_handler(program, Lists.wrap(args))
            .run(self.state)
        )

    def run_s(self, name: str, args=(), sync: bool=True) -> NvimIO[PluginState]:
        return self.run(name, args, sync).map2(lambda s, a: s)

    def run_a(self, name: str, args=(), sync: bool=True) -> NvimIO[Any]:
        return self.run(name, args, sync).map2(lambda s, a: a)

    def unsafe_run(self, name: str, args=(), sync: bool=True) -> Tuple[PluginState, Any]:
        return self.run(name, args=args, sync=sync).unsafe(self.vim)

    def unsafe_run_s(self, name: str, args=(), sync: bool=True) -> PluginState:
        return self.run_s(name, args=args, sync=sync).unsafe(self.vim)

    def unsafe_run_a(self, name: str, args=(), sync: bool=True) -> Any:
        return self.run_a(name, args=args, sync=sync).unsafe(self.vim)

    def update_data(self, **kw: Any) -> 'RequestHelper[S, D, CC]':
        return lens.state.data.modify(__.copy(**kw))(self)

    def update_component(self, name: str, **kw: Any) -> 'RequestHelper[S, D, CC]':
        return self.mod.state(__.modify_component_data(name, __.copy(**kw)))

    def component_res(self, data: C) -> Resources[S, C, CC]:
        return self.state.resources_with(ComponentData(self.state.data, data))

    def component_res_for(self, name: str) -> Resources[S, C, CC]:
        data = self.state.data_by_name(name).get_or_raise()
        return self.state.resources_with(ComponentData(self.state.data, data))

    def k(self, f: Callable[..., NvimIO[A]], *a: Any, **kw: Any) -> Expectable:
        return kn(self.vim, f, *a, **kw)

    def k_s(self, prog: str, *a: Any, **kw: Any) -> Expectable:
        return self.k(self.run_s, prog, a, **kw)


def request_helper(
        config: Config[S, D, CC],
        *comps: str,
        vars: dict=dict(),
        io_interpreter: ProgInt=None,
) -> NvimIO[RequestHelper[S, D, CC]]:
    return N.delay(lambda v: RequestHelper.nvim(config, v, *comps, vars=vars, io_interpreter=io_interpreter))


__all__ = ('RequestHelper', 'request_helper')
