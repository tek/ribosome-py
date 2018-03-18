from typing import Callable, Tuple, Any, TypeVar, Generic

from ribosome.nvim import NvimIO, NvimFacade
from ribosome.plugin_state import PluginState, PluginStateHolder, DispatchConfig

from toolz import assoc

from amino import Lists, Map, Just, List, __
from amino.dat import Dat
from amino.lenses.lens import lens
from ribosome.dispatch.run import DispatchJob
from ribosome.dispatch.data import Dispatch, DispatchResult, DIO
from ribosome.test.spec import MockNvimFacade
from ribosome.host import init_state, dispatch_job
from ribosome.dispatch.execute import (sync_runner, async_runner, SyncSender, run_dispatch, Res, execute_async_loop,
                                       async_sender, dispatch_state)
from ribosome.nvim.io import NvimIOState, NS
from ribosome.config.config import Config, Resources
from ribosome.trans.run import TransComplete
from ribosome.config.settings import Settings
from ribosome.dispatch.component import ComponentData

C = TypeVar('C')
D = TypeVar('D')
S = TypeVar('S', bound=Settings)
CC = TypeVar('CC')
IOExec = Callable[[DIO], NS[PluginState[S, D, CC], TransComplete]]


class DispatchHelper(Generic[S, D, CC], Dat['DispatchHelper']):

    @staticmethod
    def create(
            config: Config[S, D, CC],
            *comps: str,
            vars: dict=dict(),
            cons_vim: Callable[[dict], NvimFacade],
            io_executor: IOExec=None,
    ) -> 'DispatchHelper':
        comps_var = (f'{config.name}_components', Lists.wrap(comps))
        vim = cons_vim(assoc(vars, *comps_var))
        dc = DispatchConfig.cons(config, io_executor=io_executor)
        state = init_state(dc).unsafe(vim)
        return DispatchHelper(vim, dc, state)

    @staticmethod
    def nvim(
            config: Config,
            vim: NvimFacade,
            *comps: str,
            vars: dict=dict(),
            io_executor: IOExec=None,
    ) -> 'DispatchHelper':
        def cons_vim(vars: dict) -> NvimFacade:
            for k, v in vars.items():
                vim.vars.set(k, v)
            return vim
        return DispatchHelper.create(config, *comps, vars=vars, cons_vim=cons_vim, io_executor=io_executor)

    @staticmethod
    def mock(
            config: Config,
            *comps: str,
            vars: dict=dict(),
            responses: Callable[[str], Map[str, Any]]=lambda a: Just(0),
            io_executor: Callable[[DIO], NS[PluginState[S, D, CC], TransComplete]]=None,
    ) -> 'DispatchHelper':
        cons_vim = lambda vs: MockNvimFacade(prefix=config.name, vars=vs, responses=responses)
        return DispatchHelper.create(config, *comps, vars=vars, cons_vim=cons_vim, io_executor=io_executor)

    cons = mock

    def __init__(self, vim: MockNvimFacade, dispatch_config: DispatchConfig, state: PluginState[S, D, CC]) -> None:
        self.vim = vim
        self.dispatch_config = dispatch_config
        self.state = state

    @property
    def holder(self) -> PluginStateHolder[D]:
        return PluginStateHolder.strict(self.state)

    @property
    def settings(self) -> S:
        return self.state.settings

    def dispatch_job(self, name: str, args: tuple, sync: bool=True) -> Tuple[DispatchJob, Dispatch]:
        job = dispatch_job(self.holder, name, (args,), sync)
        dc = job.state.state.dispatch_config
        dispatch = dc.sync_dispatch if sync else dc.async_dispatch
        return job, dispatch.lift(job.name).get_or_fail(f'no matching dispatch for `{job.name}`')

    def sync_sender(self, name: str, args: tuple=(), sync: bool=True) -> Callable[[], Res]:
        job, dispatch = self.dispatch_job(name, args, sync)
        return SyncSender(dispatch, Lists.wrap(args), sync_runner)

    def async_sender(self, name: str, args: tuple=(), sync: bool=True) -> Callable[[], Res]:
        job, dispatch = self.dispatch_job(name, args, sync)
        return async_sender(Lists.wrap(args), dispatch, async_runner)

    def sender(self, name: str, args: tuple=(), sync: bool=True) -> Callable[[], Res]:
        s = self.sync_sender if sync else self.async_sender
        return s(name, args, sync)

    def run(self, name: str, args: tuple=(), sync: bool=True) -> NvimIOState[PluginState, DispatchResult]:
        send = self.sender(name, args, sync)
        return run_dispatch(send)

    def loop(self, name: str, args: tuple=(), sync: bool=True) -> NvimIO[PluginState]:
        job, dispatch = self.dispatch_job(name, args, sync)
        ds = List(dispatch) if sync else dispatch
        return execute_async_loop(job, ds)

    def run_s(self, name: str, args=(), sync: bool=True) -> NvimIO[Tuple[PluginState, DispatchResult]]:
        job, dispatch = self.dispatch_job(name, args, sync)
        return self.run(name, args=args, sync=sync).run(dispatch_state(self.state, dispatch.aff))

    def unsafe_run(self, name: str, args=(), sync: bool=True) -> Tuple[PluginState, DispatchResult]:
        return self.run_s(name, args=args, sync=sync).unsafe(self.vim)

    def update_data(self, **kw: Any) -> 'DispatchHelper[S, D, CC]':
        return lens.state.data.modify(__.copy(**kw))(self)

    def update_component(self, name: str, **kw: Any) -> 'DispatchHelper[S, D, CC]':
        return self.mod.state(__.modify_component_data(name, __.copy(**kw)))

    def component_res(self, data: C) -> Resources[S, C, CC]:
        return self.state.resources_with(ComponentData(self.state.data, data))


def dispatch_helper(
        config: Config[S, D, CC],
        *comps: str,
        vars: dict=dict(),
        io_executor: IOExec=None,
) -> NvimIO[DispatchHelper[S, D, CC]]:
    return NvimIO.delay(lambda v: DispatchHelper.nvim(config, v, *comps, vars=vars, io_executor=io_executor))


__all__ = ('DispatchHelper', 'dispatch_helper')
