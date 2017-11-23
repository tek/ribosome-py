from kallikrein import Expectation, kf, k
from kallikrein.matchers.either import be_right
from kallikrein.matchers.maybe import be_just
from kallikrein.matchers.length import have_length

from amino.test.spec import SpecBase
from amino import Lists, Map, List, Nothing, _

from ribosome.test.spec import MockNvimFacade
from ribosome.config import Config, AutoData
from ribosome import command
from ribosome.trans.message_base import Msg, Message
from ribosome.dispatch.component import Component
from ribosome.trans.api import trans
from ribosome.plugin_state import PluginStateHolder, handlers
from ribosome.request.handler.handler import RequestHandler
from ribosome.dispatch.data import DispatchError
from ribosome.host import host_config, request_handler, init_state, dispatch_job
from ribosome.dispatch.handle import execute_async_loop, run_dispatch, sync_sender, sync_runner, async_runner
from ribosome.nvim.io import NvimIOState
from ribosome.dispatch.resolve import ComponentResolver


specimen = Lists.random_string()


class M1(Msg):

    def __init__(self, a: int, b: str) -> None:
        self.a = a
        self.b = b


class M2(Msg):
    pass


class P(Component):

    @trans.msg.one(M1)
    def m1(self) -> Message:
        return M2()

    @trans.msg.unit(M2)
    def m2(self) -> None:
        pass


class Q(Component):

    @trans.msg.one(M1)
    def m1(self) -> str:
        return M2()


class HS:
    prefix = 'hs'

    @command(sync=True)
    def hs(self, *args) -> str:
        return specimen


class HSData(AutoData):
    pass


@trans.free.one()
def trans_free() -> Message:
    return M1(27, specimen)


config = Config(
    'hs',
    components=Map(p=P, q=Q),
    request_handlers=List(
        RequestHandler.msg_cmd(M1)('muh'),
        RequestHandler.trans_cmd(trans_free)('trfree'),
    ),
)
host_conf = host_config(config, HS, True)


# TODO test free trans function with invalid arg count
class DispatchSpec(SpecBase):
    '''
    resolve component handlers $handlers
    send a request to a legacy handler with @command decorator $legacy
    send a message $send_message
    error when arguments don't match a message constructor $msg_arg_error
    run a free trans function that returns a message $trans_free
    '''

    def handlers(self) -> Expectation:
        vim = MockNvimFacade(prefix='hs', vars=dict(hs_components=List('p', 'q')))
        components = ComponentResolver(config).run.unsafe(vim)
        return k(components.head / handlers).must(be_just(have_length(2)))

    def legacy(self) -> Expectation:
        vim = MockNvimFacade()
        state = init_state(host_conf).unsafe(vim)
        holder = PluginStateHolder.cons(state)
        handler = request_handler(vim, True, host_conf.sync_dispatch, holder, config)
        return kf(handler, 'hs:command:Hs', ((),)) == specimen

    def send_message(self) -> Expectation:
        vim = MockNvimFacade(prefix='hs', vars=dict(hs_components=List('p', 'q')))
        state = init_state(host_conf).unsafe(vim)
        holder = PluginStateHolder.cons(state)
        args = (27, specimen)
        name = 'hs:command:muh'
        job = dispatch_job(vim, True, host_conf.async_dispatch, holder, name, (args,))
        dispatch = job.dispatches.lift(job.name).get_or_fail('no matching dispatch')
        result = execute_async_loop(job, dispatch).unsafe(vim)
        return k(result.message_log) == List(M1(*args), M2(), M2())

    def msg_arg_error(self) -> Expectation:
        vim = MockNvimFacade(prefix='hs', vars=dict(hs_components=List('p')))
        state = init_state(host_conf).unsafe(vim)
        holder = PluginStateHolder.cons(state)
        name, args = 'hs:command:muh', ((specimen,),)
        job = dispatch_job(vim, True, host_conf.async_dispatch, holder, name, args)
        dispatch = job.dispatches.lift(job.name).get_or_fail('no matching dispatch')
        sender = sync_sender(job, dispatch, async_runner)
        result = sender().run_a(state).attempt(vim) / _.output
        err = f'argument count for command `HsMuh` is 1, must be exactly 2 ([{specimen}])'
        return k(result).must(be_right(DispatchError(err, Nothing)))

    def trans_free(self) -> Expectation:
        vim = MockNvimFacade(prefix='hs', vars=dict(hs_components=List('p', 'q')))
        state = init_state(host_conf).unsafe(vim)
        holder = PluginStateHolder.cons(state)
        name = 'hs:command:trfree'
        job = dispatch_job(vim, True, host_conf.async_dispatch, holder, name, (()))
        dispatch = job.dispatches.lift(job.name).get_or_fail('no matching dispatch')
        result = run_dispatch(sync_sender(job, dispatch, sync_runner), NvimIOState.pure).run_s(state).unsafe(vim)
        return k(result.message_log) == List()

__all__ = ('DispatchSpec',)
