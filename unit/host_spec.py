from kallikrein import Expectation, kf

from amino.test.spec import SpecBase
from amino import Nil, Lists

from ribosome.test.spec import MockNvimFacade
from ribosome.host import request_handler, host_config
from ribosome.config import Config, AutoData
from ribosome.request.dispatch import PluginState, PluginStateHolder
from ribosome.machine.process_messages import PrioQueue
from ribosome import command


specimen = Lists.random_string()


class HS:
    prefix = 'hs'

    @command(sync=True)
    def hs(self, *args) -> int:
        return specimen


class HSData(AutoData):
    pass


config = Config('hs')
host_conf = host_config(config, HS, True)


class HostSpec(SpecBase):
    '''
    send a request to a legacy handler with @command decorator $legacy
    '''

    def legacy(self) -> Expectation:
        vim = MockNvimFacade()
        data = HSData(config=config)
        state = PluginState.cons(vim, data, host_conf.plugin_class(vim, data), Nil, PrioQueue.empty)
        holder = PluginStateHolder.cons(state)
        handler = request_handler(vim, True, host_conf.sync_dispatch, holder, config)
        return kf(handler, 'hs:command:Hs', ()) == specimen

__all__ = ('HostSpec',)
