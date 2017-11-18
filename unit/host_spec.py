from kallikrein import Expectation, kf, k
from kallikrein.matchers.either import be_right
from kallikrein.matchers import equal

from amino.test.spec import SpecBase
from amino import Nil, Lists, Map, List, Nothing

from ribosome.test.spec import MockNvimFacade
from ribosome.host import request_handler, host_config, dispatch_job, execute, execute_async, execute_async_loop
from ribosome.config import Config, AutoData
from ribosome.machine.process_messages import PrioQueue
from ribosome import command
from ribosome.machine.message_base import Msg
from ribosome.machine.sub import Component
from ribosome.machine import trans
from ribosome.plugin_state import PluginState, PluginStateHolder
from ribosome.request.handler.handler import RequestHandler
from ribosome.request.dispatch.data import DispatchError


specimen = Lists.random_string()


class M1(Msg):

    def __init__(self, a: int, b: str) -> None:
        self.a = a
        self.b = b


class M2(Msg):
    pass


class P(Component):

    @trans.one(M1)
    def m1(self) -> str:
        return M2()

    @trans.unit(M2)
    def m2(self) -> str:
        pass


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
        RequestHandler.msg_cmd(M1)('muh'),
    ),
)
host_conf = host_config(config, HS, True)


class HostSpec(SpecBase):
    '''
    send a request to a legacy handler with @command decorator $legacy
    send a message $send_message
    error when arguments don't match a message constructor $msg_arg_error
    '''

    def legacy(self) -> Expectation:
        vim = MockNvimFacade()
        data = HSData(config=config)
        state = PluginState.cons(vim, data, host_conf.plugin_class(vim, data), Nil, PrioQueue.empty)
        holder = PluginStateHolder.cons(state)
        handler = request_handler(vim, True, host_conf.sync_dispatch, holder, config)
        return kf(handler, 'hs:command:Hs', ((),)) == specimen

    def send_message(self) -> Expectation:
        vim = MockNvimFacade(prefix='hs', vars=dict(hs_components=List('p')))
        data = HSData(config=config)
        state = PluginState.cons(vim, data, host_conf.plugin_class(vim, data), Nil, PrioQueue.empty)
        holder = PluginStateHolder.cons(state)
        name, args = 'hs:command:muh', ((27, specimen,),)
        job = dispatch_job(vim, True, host_conf.async_dispatch, holder, name, args)
        dispatch = job.dispatches.lift(job.name).get_or_raise('no matching dispatch')
        result = execute_async_loop(job, dispatch).attempt(vim).get_or_raise()
        return k(result).must(equal(None))

    def msg_arg_error(self) -> Expectation:
        vim = MockNvimFacade(prefix='hs', vars=dict(hs_components=List('p')))
        data = HSData(config=config)
        state = PluginState.cons(vim, data, host_conf.plugin_class(vim, data), Nil, PrioQueue.empty)
        holder = PluginStateHolder.cons(state)
        name, args = 'hs:command:muh', ((specimen,),)
        job = dispatch_job(vim, True, host_conf.async_dispatch, holder, name, args)
        dispatch = job.dispatches.lift(job.name).get_or_raise('no matching dispatch')
        io = execute(job, dispatch)
        err = f'argument count for command `HsMuh` is 1, must be exactly 2 ([{specimen}])'
        return kf(io.attempt, vim).must(be_right(DispatchError(err, Nothing)))

__all__ = ('HostSpec',)
