from typing import Tuple, Callable

from kallikrein import Expectation, kf, k
from kallikrein.matchers.either import be_right
from kallikrein.matchers.maybe import be_just
from kallikrein.matchers.length import have_length

from amino.test.spec import SpecBase
from amino import Lists, Map, List, Nothing, _, IO

from ribosome.test.spec import MockNvimFacade
from ribosome.config import Config, AutoData
from ribosome import command
from ribosome.trans.message_base import Msg, Message
from ribosome.dispatch.component import Component
from ribosome.trans.api import trans
from ribosome.plugin_state import PluginStateHolder, handlers, PluginState
from ribosome.request.handler.handler import RequestHandler
from ribosome.dispatch.data import DispatchError, Dispatch, DispatchResult
from ribosome.host import host_config, request_handler, init_state, dispatch_job
from ribosome.dispatch.handle import execute_async_loop, run_dispatch, sync_sender, sync_runner, async_runner
from ribosome.nvim.io import NvimIOState
from ribosome.dispatch.resolve import ComponentResolver
from ribosome.nvim import NvimFacade
from ribosome.dispatch.run import DispatchJob


specimen = Lists.random_string()


class M1(Msg):

    def __init__(self, a: int, b: str) -> None:
        self.a = a
        self.b = b


m1 = M1(27, specimen)


class M2(Msg): pass


class M3(Msg): pass


class P(Component):

    @trans.msg.one(M1)
    def m1(self) -> Message:
        return M2()

    @trans.msg.one(M2, trans.io)
    def m2(self) -> IO[Message]:
        return IO.pure(M3())


class Q(Component):

    @trans.msg.one(M1)
    def m1(self) -> str:
        return M2()

    @trans.msg.one(M2, trans.io)
    def m2(self) -> IO[Message]:
        return IO.pure(m1)


class HS:
    prefix = 'hs'

    @command(sync=True)
    def hs(self, *args) -> str:
        return specimen


class HSData(AutoData):
    pass


@trans.free.one()
def trans_free() -> Message:
    return m1


@trans.free.one(trans.io)
def trans_io() -> IO[Message]:
    return IO.pure(m1)


config = Config(
    'hs',
    components=Map(p=P, q=Q),
    request_handlers=List(
        RequestHandler.msg_cmd(M1)('muh'),
        RequestHandler.msg_cmd(M2)('meh'),
        RequestHandler.trans_cmd(trans_free)('trfree'),
        RequestHandler.trans_cmd(trans_io)('trio'),
    ),
)
host_conf = host_config(config, HS, True)


def init(name: str, *comps: str, args=()) -> Tuple[NvimFacade, PluginState, DispatchJob, Dispatch]:
    vim = MockNvimFacade(prefix='hs', vars=dict(hs_components=Lists.wrap(comps)))
    state = init_state(host_conf).unsafe(vim)
    holder = PluginStateHolder.cons(state)
    job = dispatch_job(vim, True, host_conf.async_dispatch, holder, name, (args,))
    return vim, state, job, job.dispatches.lift(job.name).get_or_fail('no matching dispatch')


def sender(name: str, *comps: str, args=(), sync=True) -> Tuple[PluginState, NvimFacade, Callable]:
    vim, state, job, dispatch = init(name, *comps, args=args)
    runner = sync_runner if sync else async_runner
    return state, vim, sync_sender(job, dispatch, runner)


def run(name: str, *comps: str, args=(), sync=True) -> Tuple[PluginState, DispatchResult]:
    state, vim, send = sender(name, *comps, args=args, sync=sync)
    return run_dispatch(send, NvimIOState.pure).run(state).unsafe(vim)


# TODO test free trans function with invalid arg count
class DispatchSpec(SpecBase):
    '''
    resolve component handlers $handlers
    send a request to a legacy handler with @command decorator $legacy
    send a message $send_message
    error when arguments don't match a message constructor $msg_arg_error
    run a free trans function that returns a message $trans_free
    run an IO result from a free trans $io
    aggregate IO results from multiple components $multi_io
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
        args = (27, specimen)
        vim, state, job, dispatch = init('hs:command:muh', 'p', 'q', args=args)
        result = execute_async_loop(job, dispatch).unsafe(vim)
        return k(result.message_log) == List(M1(*args), M2(), M2())

    def msg_arg_error(self) -> Expectation:
        name, args = 'hs:command:muh', (specimen,)
        state, vim, send = sender(name, 'p', args=args, sync=False)
        result = send().run_a(state).attempt(vim) / _.output
        err = f'argument count for command `HsMuh` is 1, must be exactly 2 ([{specimen}])'
        return k(result).must(be_right(DispatchError(err, Nothing)))

    def trans_free(self) -> Expectation:
        state, result = run('hs:command:trfree', 'p', 'q')
        return k(state.message_log) == List()

    def io(self) -> Expectation:
        state, result = run('hs:command:trio')
        return k(state.messages.items.head / _[1] / _.message).must(be_just(m1))

    def multi_io(self) -> Expectation:
        state, result = run('hs:command:meh', 'p', 'q', sync=False)
        return k(state.unwrapped_messages) == List(m1, M3())

__all__ = ('DispatchSpec',)
