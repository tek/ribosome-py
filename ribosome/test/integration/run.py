from typing import Callable, Tuple, Any, TypeVar

from ribosome.nvim import NvimIO
from ribosome.plugin_state import PluginState, PluginStateHolder

from toolz import assoc

from amino import Lists, Left, Map, Just
from amino.boolean import true
from amino.dat import Dat
from ribosome.dispatch.run import DispatchJob
from ribosome.dispatch.data import Dispatch, DispatchResult, DIO
from ribosome.test.spec import MockNvimFacade
from ribosome.host import init_state, dispatch_job, HostConfig, host_config
from ribosome.dispatch.execute import sync_runner, async_runner, sync_sender, run_dispatch, Res, execute_async_loop
from ribosome.nvim.io import NvimIOState, NS
from ribosome.config import Config
from ribosome.trans.handler import TransComplete

D = TypeVar('D')


class DispatchHelper(Dat['DispatchHelper']):

    @staticmethod
    def cons(
            config: Config,
            *comps: str,
            vars: dict=dict(),
            responses: Callable[[str], Map[str, Any]]=lambda a: Just(0),
            io_executor: Callable[[DIO], NS[PluginState[D], TransComplete]]=None,
    ) -> 'DispatchHelper':
        hc = host_config(config, Left('spec'), true, io_executor)
        comps_var = (f'{config.name}_components', Lists.wrap(comps))
        vim = MockNvimFacade(prefix=config.name, vars=assoc(vars, *comps_var), responses=responses)
        state = init_state(hc).unsafe(vim)
        return DispatchHelper(vim, hc, state)

    def __init__(self, vim: MockNvimFacade, host_conf: HostConfig, state: PluginState) -> None:
        self.vim = vim
        self.host_conf = host_conf
        self.state = state

    def dispatch(self, name: str, args: tuple) -> Tuple[DispatchJob, Dispatch]:
        holder = PluginStateHolder.strict(self.state)
        job = dispatch_job(True, self.host_conf.config.async_dispatch, holder, name, self.state.config.prefix, (args,))
        return job, job.dispatches.lift(job.name).get_or_fail('no matching dispatch')

    def sender(self, name: str, args: tuple=(), sync: bool=True) -> Callable[[], Res]:
        job, dispatch = self.dispatch(name, args)
        runner = sync_runner if sync else async_runner
        return sync_sender(job, dispatch, runner)

    def run(self, name: str, args: tuple=(), sync: bool=True) -> NvimIOState[PluginState, DispatchResult]:
        send = self.sender(name, args, sync)
        return run_dispatch(send, NvimIOState.pure)

    def loop(self, name: str, args: tuple=(), sync: bool=True) -> NvimIO[Tuple[PluginState, DispatchResult]]:
        job, dispatch = self.dispatch(name, args)
        return execute_async_loop(job, dispatch)

    def unsafe_run(self, name: str, args=(), sync: bool=True) -> Tuple[PluginState, DispatchResult]:
        return self.run(name, args=args, sync=sync).run(self.state).unsafe(self.vim)


__all__ = ('DispatchHelper',)
