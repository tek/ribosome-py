from kallikrein import Expectation, kf
from kallikrein.matchers.either import be_right

from amino.test.spec import SpecBase
from amino import Nil, Lists, Map, List, Nothing

from ribosome.test.spec import MockNvimFacade
from ribosome.host import request_handler, host_config, dispatch_job, dispatch_request
from ribosome.config import Config, AutoData
from ribosome.request.dispatch import PluginState, PluginStateHolder, DispatchError
from ribosome.machine.process_messages import PrioQueue
from ribosome import command
from ribosome.request.handler import RequestHandler
from ribosome.machine.message_base import Msg
from ribosome.machine.sub import Component
from ribosome.machine import trans


specimen = Lists.random_string()


class M1(Msg):

    def __init__(self, a: int, b: str) -> None:
        self.a = a
        self.b = b


class P(Component):

    @trans.plain(M1, trans.result)
    def target(self) -> str:
        return specimen


class HS:
    prefix = 'hs'

    @command(sync=True)
    def hs(self, *args) -> str:
        return specimen


class HSData(AutoData):
    pass


config = Config(
    'hs',
    components=Map(p=P),
    request_handlers=List(
        RequestHandler.msg_cmd(M1)('muh', sync=True),
    ),
)
host_conf = host_config(config, HS, True)


class HostSpec(SpecBase):
    '''
    send a request to a legacy handler with @command decorator $legacy
    error when arguments don't match a message constructor $msg_arg_error
    '''

    def legacy(self) -> Expectation:
        vim = MockNvimFacade()
        data = HSData(config=config)
        state = PluginState.cons(vim, data, host_conf.plugin_class(vim, data), Nil, PrioQueue.empty)
        holder = PluginStateHolder.cons(state)
        handler = request_handler(vim, True, host_conf.sync_dispatch, holder, config)
        return kf(handler, 'hs:command:Hs', ((),)) == specimen

    def msg_arg_error(self) -> Expectation:
        vim = MockNvimFacade(prefix='hs', vars=dict(hs_components=List('p')))
        data = HSData(config=config)
        state = PluginState.cons(vim, data, host_conf.plugin_class(vim, data), Nil, PrioQueue.empty)
        holder = PluginStateHolder.cons(state)
        name, args = 'hs:command:muh', ((specimen,),)
        job = dispatch_job(vim, True, host_conf.sync_dispatch, holder, name, args)
        err = f'argument count for command `HsMuh` is 1, must be exactly 2 ([{specimen}])'
        io = dispatch_request(job)
        return kf(io.attempt, vim).must(be_right(DispatchError(err, Nothing)))

__all__ = ('HostSpec',)
