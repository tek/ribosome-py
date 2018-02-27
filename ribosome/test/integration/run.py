from typing import Callable, Tuple, Any, TypeVar, Generic

from ribosome.nvim import NvimIO
from ribosome.plugin_state import PluginState, PluginStateHolder, DispatchConfig

from toolz import assoc

from amino import Lists, Map, Just, List, __
from amino.dat import Dat
from amino.lenses.lens import lens
from ribosome.dispatch.run import DispatchJob
from ribosome.dispatch.data import Dispatch, DispatchResult, DIO
from ribosome.test.spec import MockNvimFacade
from ribosome.host import init_state, dispatch_job
from ribosome.dispatch.execute import (sync_runner, async_runner, sync_sender, run_dispatch, Res, execute_async_loop,
                                       async_sender, dispatch_state)
from ribosome.nvim.io import NvimIOState, NS
from ribosome.config.config import Config
from ribosome.trans.run import TransComplete
from ribosome.config.settings import Settings

D = TypeVar('D')
S = TypeVar('S', bound=Settings)
CC = TypeVar('CC')


class DispatchHelper(Generic[S, D, CC], Dat['DispatchHelper']):

    @staticmethod
    def cons(
            config: Config,
            *comps: str,
            vars: dict=dict(),
            responses: Callable[[str], Map[str, Any]]=lambda a: Just(0),
            io_executor: Callable[[DIO], NS[PluginState[S, D, CC], TransComplete]]=None,
    ) -> 'DispatchHelper':
        dc = DispatchConfig.cons(config, io_executor=io_executor)
        comps_var = (f'{config.name}_components', Lists.wrap(comps))
        vim = MockNvimFacade(prefix=config.name, vars=assoc(vars, *comps_var), responses=responses)
        state = init_state(dc).unsafe(vim)
        return DispatchHelper(vim, dc, state)

    def __init__(self, vim: MockNvimFacade, dispatch_config: DispatchConfig, state: PluginState[S, D, CC]) -> None:
        self.vim = vim
        self.dispatch_config = dispatch_config
        self.state = state

    @property
    def holder(self) -> PluginStateHolder[D]:
        return PluginStateHolder.strict(self.state)

    def dispatch_job(self, name: str, args: tuple, sync: bool=True) -> Tuple[DispatchJob, Dispatch]:
        job = dispatch_job(self.holder, name, (args,), sync)
        dc = job.state.state.dispatch_config
        dispatch = dc.sync_dispatch if sync else dc.async_dispatch
        return job, dispatch.lift(job.name).get_or_fail('no matching dispatch')

    def sync_sender(self, name: str, args: tuple=(), sync: bool=True) -> Callable[[], Res]:
        job, dispatch = self.dispatch_job(name, args, sync)
        return sync_sender(Lists.wrap(args), dispatch, sync_runner)

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

    def unsafe_run(self, name: str, args=(), sync: bool=True) -> Tuple[PluginState, DispatchResult]:
        job, dispatch = self.dispatch_job(name, args, sync)
        return self.run(name, args=args, sync=sync).run(dispatch_state(self.state, dispatch)).unsafe(self.vim)

    def update_data(self, **kw: Any) -> 'DispatchHelper[S, D, CC]':
        return lens.state.data.modify(__.copy(**kw))(self)

    def update_component(self, name: str, **kw: Any) -> 'DispatchHelper[S, D, CC]':
        return self.mod.state(__.modify_component_data(name, __.copy(**kw)))


__all__ = ('DispatchHelper',)
