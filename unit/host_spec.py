from kallikrein import Expectation, kf, k
from kallikrein.matchers.either import be_right

from amino.test.spec import SpecBase
from amino import Nil, Lists, Map, List, Nothing

from ribosome.test.spec import MockNvimFacade
from ribosome.config import Config, AutoData
from ribosome.machine.process_messages import PrioQueue
from ribosome import command
from ribosome.machine.message_base import Msg
from ribosome.machine.sub import Component
from ribosome.machine import trans
from ribosome.plugin_state import PluginState, PluginStateHolder
from ribosome.request.handler.handler import RequestHandler
from ribosome.request.dispatch.data import DispatchError
from ribosome.host import host_config, request_handler, init_state, dispatch_job
from ribosome.request.dispatch.handle import execute_async_loop, execute


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
        print('m2')


class Q(Component):

    @trans.one(M1)
    def m1(self) -> str:
        return M2()


class HS:
    prefix = 'hs'

    @command(sync=True)
    def hs(self, *args) -> str:
        return specimen


class HSData(AutoData):
    pass


config = Config(
    'hs',
    components=Map(p=P, q=Q),
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
        state = init_state(host_conf).attempt(vim).get_or_raise()
        holder = PluginStateHolder.cons(state)
        handler = request_handler(vim, True, host_conf.sync_dispatch, holder, config)
        return kf(handler, 'hs:command:Hs', ((),)) == specimen

    def send_message(self) -> Expectation:
        vim = MockNvimFacade(prefix='hs', vars=dict(hs_components=List('p', 'q')))
        state = init_state(host_conf).attempt(vim).get_or_raise()
        holder = PluginStateHolder.cons(state)
        args = (27, specimen)
        name = 'hs:command:muh'
        job = dispatch_job(vim, True, host_conf.async_dispatch, holder, name, (args,))
        dispatch = job.dispatches.lift(job.name).get_or_raise('no matching dispatch')
        result = execute_async_loop(job, dispatch).attempt(vim).get_or_raise()
        return k(result.message_log) == List(M1(*args), M2(), M2())

    def msg_arg_error(self) -> Expectation:
        vim = MockNvimFacade(prefix='hs', vars=dict(hs_components=List('p')))
        state = init_state(host_conf).attempt(vim).get_or_raise()
        holder = PluginStateHolder.cons(state)
        name, args = 'hs:command:muh', ((specimen,),)
        job = dispatch_job(vim, True, host_conf.async_dispatch, holder, name, args)
        dispatch = job.dispatches.lift(job.name).get_or_raise('no matching dispatch')
        io = execute_async_loop(job, dispatch)
        err = f'argument count for command `HsMuh` is 1, must be exactly 2 ([{specimen}])'
        return kf(io.attempt, vim).must(be_right(DispatchError(err, Nothing)))

__all__ = ('HostSpec',)
