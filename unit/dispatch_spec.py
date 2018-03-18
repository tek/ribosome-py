from kallikrein import Expectation, k, pending
from kallikrein.matchers.either import be_right
from kallikrein.matchers.maybe import be_just
from kallikrein.matchers.length import have_length
from kallikrein.matchers.typed import have_type

from amino.test.spec import SpecBase
from amino import Lists, Map, List, Nothing, _, IO, __, Right
from amino.boolean import true
from amino.dat import Dat, ADT
from amino.state import State

from ribosome.trans.message_base import Msg, Message
from ribosome.dispatch.component import Component
from ribosome.trans.api import trans
from ribosome.plugin_state import PluginState, DispatchConfig
from ribosome.request.handler.handler import RequestHandler
from ribosome.dispatch.data import DispatchError, DispatchOutputAggregate
from ribosome.nvim.io import NS
from ribosome.dispatch.resolve import ComponentResolver
from ribosome.test.integration.run import DispatchHelper
from ribosome.config.config import Config
from ribosome.dispatch.execute import dispatch_state


specimen = Lists.random_string()


class M1(Msg):

    def __init__(self, a: int, b: str) -> None:
        self.a = a
        self.b = b


m1 = M1(27, specimen)


class M2(Msg): pass


class M3(Msg): pass


class M4(Msg): pass


@trans.msg.one(M1)
def p_m1(msg: M1) -> Message:
    return M2()


@trans.msg.unit(M2)
def p_m2(msg: M2) -> None:
    return None


@trans.msg.one(M3, trans.io)
def p_m3(msg: M3) -> IO[Message]:
    return IO.pure(M4())


@trans.msg.one(M1)
def q_m1(msg: M1) -> str:
    return M2()


@trans.msg.unit(M2)
def q_m2(msg: M2) -> None:
    return None


@trans.msg.one(M3, trans.io)
def q_m3(msg: M3) -> IO[Message]:
    return IO.pure(m1)


class HsData(Dat['HsData']):

    def __init__(self, counter: int=7) -> None:
        self.counter = counter


@trans.free.one()
def trans_free(a: int, b: str='b') -> Message:
    return m1


@trans.free.one(trans.io)
def trans_io() -> IO[Message]:
    return IO.pure(m1)


# TODO allow args here
@trans.free.result(trans.st)
def trans_internal() -> NS[PluginState, str]:
    return NS.inspect(_.name)


@trans.free.unit(trans.st)
def trans_data() -> NS[HsData, None]:
    return NS.modify(__.set.counter(23))


class JData(ADT['JData']):

    def __init__(self, number: int, name: str, items: List[str]) -> None:
        self.number = number
        self.name = name
        self.items = items


@trans.free.result()
def trans_json(a: int, b: str, data: JData) -> int:
    return data.number + a


@trans.free.unit(trans.st)
def vim_enter() -> State[HsData, None]:
    return State.modify(__.copy(counter=19))


P = Component.cons(
    'p',
    handlers=List(
        p_m1,
        p_m2,
        p_m3,
    )
)
Q = Component.cons(
    'q',
    handlers=List(
        q_m1,
        q_m2,
        q_m3,
    )
)
config = Config.cons(
    'hs',
    components=Map(p=P, q=Q),
    request_handlers=List(
        RequestHandler.msg_cmd(M1)('muh'),
        RequestHandler.msg_cmd(M3)('meh'),
        RequestHandler.trans_cmd(trans_free)('trfree'),
        RequestHandler.trans_cmd(trans_io)('trio'),
        RequestHandler.trans_function(trans_internal)('int'),
        RequestHandler.trans_function(trans_data)('dat'),
        RequestHandler.trans_cmd(trans_json)('json', json=true),
        RequestHandler.trans_autocmd(vim_enter)(),
    ),
    state_ctor=HsData,
)
dispatch_conf = DispatchConfig.cons(config)


# TODO test free trans function with invalid arg count
class DispatchSpec(SpecBase):
    '''
    resolve component handlers $handlers
    send a message $send_message
    error when arguments don't match a message constructor $msg_arg_error
    run a free trans function that returns a message $trans_free
    run an IO result from a free trans $io
    aggregate IO results from multiple components $multi_io
    work on PluginState in internal trans $internal
    modify the state data $data
    json command args $json
    run an autocmd $autocmd
    '''

    def handlers(self) -> Expectation:
        components = ComponentResolver(config, Right(List('p', 'q'))).run.get_or_raise()
        return k(components.lift(1) // _.handlers.v.head / _.handlers).must(be_just(have_length(3)))

    @pending
    def send_message(self) -> Expectation:
        helper = DispatchHelper.cons(config, 'p', 'q')
        args = (27, specimen)
        result = helper.loop('command:muh', args=args, sync=False).unsafe(helper.vim)
        return k(result.message_log) == List(M1(*args), M2(), M2())

    def msg_arg_error(self) -> Expectation:
        helper = DispatchHelper.cons(config, 'p')
        name, args = 'command:muh', (specimen,)
        job, dispatch = helper.dispatch_job(name, args, False)
        send = helper.sender(name, args=args, sync=False)
        result = send().run_a(dispatch_state(helper.state, dispatch)).attempt(helper.vim) / _.output
        err = f'''argument count for command `HsMuh` is 1, must be exactly 2 ([{specimen}])'''
        return (
            k(result).must(be_right(have_type(DispatchOutputAggregate))) &
            k(result / _.results // __.head.to_either('left') / _.output).must(be_right(DispatchError(err, Nothing)))
        )

    def trans_free(self) -> Expectation:
        helper = DispatchHelper.cons(config, 'p', 'q')
        state = helper.unsafe_run_s('command:trfree', args=('x',))
        return k(state.message_log) == List()

    def io(self) -> Expectation:
        helper = DispatchHelper.cons(config)
        state = helper.unsafe_run_s('command:trio')
        return k(state.messages.items.head / _[1] / _.message).must(be_just(m1))

    @pending
    def multi_io(self) -> Expectation:
        helper = DispatchHelper.cons(config, 'p', 'q')
        state = helper.unsafe_run_s('command:meh', sync=False)
        return k(state.unwrapped_messages) == List(m1, M4())

    def internal(self) -> Expectation:
        helper = DispatchHelper.cons(config)
        state, result = helper.unsafe_run('function:int')
        return k(result) == state.name

    def data(self) -> Expectation:
        helper = DispatchHelper.cons(config)
        state = helper.unsafe_run_s('function:dat')
        return k(state.data.counter) == 23

    def json(self) -> Expectation:
        helper = DispatchHelper.cons(config)
        js = '{ "number": 2, "name": "two", "items": ["1", "2", "3"] }'
        result = helper.unsafe_run_a('command:json', args=(7, 'one', *Lists.split(js, ' ')))
        return k(result) == 9

    def autocmd(self) -> Expectation:
        helper = DispatchHelper.cons(config)
        state = helper.unsafe_run_s('autocmd:vim_enter')
        return k(state.data.counter) == 19


__all__ = ('DispatchSpec',)
