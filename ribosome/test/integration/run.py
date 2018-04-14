from typing import Callable, Tuple, Any, TypeVar, Generic

from amino import Lists, Map, List, __, Either, Left, Right, do, Do, Nil
from amino.dat import Dat
from amino.lenses.lens import lens

from ribosome.host import init_state
from ribosome.request.execute import request_job, traverse_programs, run_request_handler
from ribosome.nvim.io.state import NvimIOState, NS
from ribosome.config.config import Config
from ribosome.config.settings import Settings
from ribosome.config.component import ComponentData
from ribosome.nvim.api.data import NvimApi, StrictNvimApi, StrictNvimHandler
from ribosome.nvim.io.compute import NvimIO
from ribosome.data.plugin_state import PluginState
from ribosome.nvim.api.variable import variable_set
from ribosome.nvim.io.api import N
from ribosome.request.job import RequestJob
from ribosome.compute.prog import Program
from ribosome.config.resources import Resources
from ribosome.data.plugin_state_holder import PluginStateHolder

C = TypeVar('C')
D = TypeVar('D')
S = TypeVar('S', bound=Settings)
CC = TypeVar('CC')
DIO = TypeVar('DIO')
IOExec = Callable[[DIO], NS[PluginState[S, D, CC], Any]]


def api_info(vim: NvimApi, name: str, args: List[Any]) -> Either[str, Any]:
    return Right((vim, (1, {})))


def rh_write(vim: NvimApi, name: str, args: List[Any]) -> Either[str, Any]:
    return Right((vim, None))


@do(Either[str, Any])
def default_request_handler(vim: NvimApi, name: str, args: List[Any]) -> Do:
    handler = yield default_request_handlers.lift(name).to_either(f'no default request handler for {name}')
    yield handler(vim, name, args)


@do(Either[str, Any])
def pop_first(vim: NvimApi, name: str, args: List[Any]) -> Do:
    name1, args1 = yield args.detach_head.to_either(f'invalid command: {name}({args})')
    yield default_request_handler(vim, name1, args1)


default_request_handlers = Map({
    'silent': pop_first,
    'silent!': pop_first,
    'nvim_get_api_info': api_info,
    'nvim_command': rh_write,
    'nvim_out_write': rh_write,
})


class StrictRequestHandler:

    def __init__(self, extra: StrictNvimHandler) -> None:
        self.extra = extra

    def __call__(self, vim: NvimApi, name: str, args: List[Any]) -> Either[List[str], Tuple[NvimApi, Any]]:
        return (
            self.extra(vim, name, args)
            .lmap(List)
            .accum_error_lift(default_request_handler, vim, name, args)
        )


class RequestHelper(Generic[S, D, CC], Dat['RequestHelper']):

    @staticmethod
    def create(
            config: Config[S, D, CC],
            *comps: str,
            vars: Map[str, Any]=Map(),
            cons_vim: Callable[[dict], NvimApi],
            io_executor: IOExec=None,
    ) -> 'RequestHelper':
        comps_var = Map({f'{config.basic.name}_components': Lists.wrap(comps)})
        vim = cons_vim(vars ** comps_var)
        vim1, state = init_state(config, io_executor=io_executor).unsafe_run(vim)
        return RequestHelper(vim, config, state)

    @staticmethod
    def nvim(
            config: Config,
            vim: NvimApi,
            *comps: str,
            vars: dict=dict(),
            io_executor: IOExec=None,
    ) -> 'RequestHelper':
        def cons_vim(vars: dict) -> NvimApi:
            for k, v in vars.items():
                variable_set(k, v).unsafe(vim)
            return vim
        return RequestHelper.create(config, *comps, vars=Map(vars), cons_vim=cons_vim, io_executor=io_executor)

    @staticmethod
    def strict(
            config: Config,
            *comps: str,
            vars: Map[str, Any]=Map(),
            request_handler: StrictNvimHandler=lambda v, n, a: Left(f'no handler for {n}'),
            io_executor: Callable[[DIO], NS[PluginState[S, D, CC], Any]]=None,
    ) -> 'RequestHelper':
        cons_vim = lambda vs: StrictNvimApi(config.basic.name, vs, StrictRequestHandler(request_handler), Nil)
        return RequestHelper.create(config, *comps, vars=vars, cons_vim=cons_vim, io_executor=io_executor)

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

    def traverse_programs(self, name: str, args: tuple=(), sync: bool=True) -> NvimIOState[PluginState[S, D, CC], Any]:
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


def request_helper(
        config: Config[S, D, CC],
        *comps: str,
        vars: dict=dict(),
        io_executor: IOExec=None,
) -> NvimIO[RequestHelper[S, D, CC]]:
    return N.delay(lambda v: RequestHelper.nvim(config, v, *comps, vars=vars, io_executor=io_executor))


__all__ = ('DispatchHelper', 'request_helper')
