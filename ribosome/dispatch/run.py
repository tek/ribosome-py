from typing import TypeVar, Any, Generic, Type, Callable, Tuple, Union

from amino import List, Boolean, Either, Left, Right, __, Maybe, Lists, Nothing, _
from amino.dat import Dat
from amino.do import do, Do
from amino.dispatch import dispatch_alg
from amino.state import StateT

from ribosome.nvim import NvimIO
from ribosome.logging import Logging
from ribosome.request.args import ArgValidator, ParamsSpec
from ribosome.plugin_state import PluginState, PluginStateHolder, DispatchAffiliation, RootDispatch, ComponentDispatch
from ribosome.dispatch.data import Trans, SendMessage, DispatchResult, Dispatch
from ribosome.nvim.io import NS
from ribosome.trans.message_base import Message
from ribosome.dispatch.transform import validate_trans_complete
from ribosome.trans.send_message import send_message
from ribosome.trans.handler import FreeTrans
from ribosome.dispatch.component import ComponentData
from ribosome.request.handler.handler import RequestHandler
from ribosome.request.handler.dispatcher import RequestDispatcher
from ribosome.config.settings import Settings
from ribosome.config.config import Resources
from ribosome.trans.run import run_free_trans_handler

NP = TypeVar('NP')
D = TypeVar('D')
DP = TypeVar('DP', bound=Dispatch)
S = TypeVar('S', bound=Settings)
CC = TypeVar('CC')
Res = NS[PluginState[S, D, CC], DispatchResult]
St = TypeVar('St')
C = TypeVar('C')
E = TypeVar('E')
R = TypeVar('R')
TD = Union[PluginState[S, D, CC], Resources[S, D, CC], D]
TT = Union[TD, ComponentData[TD, C]]


class DispatchState(Generic[S, D, CC], Dat['DispatchState']):

    def __init__(self, state: PluginState[S, D, CC], aff: DispatchAffiliation) -> None:
        self.state = state
        self.aff = aff


DRes = NS[DispatchState[S, D, CC], DispatchResult]


def dispatch_to_plugin(st: NS[DispatchState[S, D, CC], R], aff: DispatchAffiliation) -> NS[PluginState[S, D, CC], R]:
    return st.transform_s(lambda r: DispatchState(r, aff), lambda r, s: s.state)


def plugin_to_dispatch(st: NS[PluginState[S, D, CC], R]) -> NS[DispatchState[S, D, CC], R]:
    return st.transform_s(lambda r: r.state, lambda r, s: r.copy(state=s))


def log_trans(trans: FreeTrans) -> NS[PluginState[S, D, CC], None]:
    return NS.pure(None) if trans.name in ('trans_log', 'pure') else NS.modify(__.log_trans(trans.name))


def execute_trans(handler: FreeTrans) -> NS[D, DispatchResult]:
    return validate_trans_complete(run_free_trans_handler(handler))


def parse_args(handler: RequestHandler, dispatcher: RequestDispatcher, args: List[Any]) -> NS[D, List[Any]]:
    return handler.parser(dispatcher.params_spec).parse(args)


@do(Res)
def setup_trans(dispatch: Dispatch, args: List[Any]) -> Do:
    dispatcher = dispatch.handler.dispatcher
    parsed_args = yield NS.from_either(parse_args(dispatch.handler, dispatcher, args))
    yield plugin_to_dispatch(log_trans(dispatch))
    yield NS.pure(dispatcher.handler(*parsed_args))


AWWrap = Callable[[PluginState[S, D, CC], TD], TT]
AWUnwrap = Callable[[TT], TD]
AWStore = Callable[[TT, PluginState[S, D, CC]], PluginState[S, D, CC]]
AWR = Tuple[AWWrap, AWUnwrap, AWStore]


# FIXME `wrap` should return an ADT that is dispatched in unwrap
# should have an abstract `update` method that is used deeper down
class AffiliationWrapper:

    def root_dispatch(self, aff: RootDispatch, handler: FreeTrans) -> AWR:
        def wrap(r: PluginState[S, D, CC], b: TD) -> TT:
            return b
        def unwrap(r: TT) -> TD:
            return r
        def store(r: TT, s: PluginState[S, D, CC]) -> PluginState[S, D, CC]:
            return s
        return wrap, unwrap, store

    def component_dispatch(self, aff: ComponentDispatch, handler: FreeTrans) -> AWR:
        return (
            self._component_dispatch(aff, handler)
            if handler.component else
            self.root_dispatch(RootDispatch(), handler)
        )

    def _component_dispatch(self, aff: ComponentDispatch, handler: FreeTrans) -> AWR:
        def wrap(original: PluginState[S, D, CC], wrapped: TD) -> TT:
            return ComponentData(wrapped, original.data_for(aff.component))
        def unwrap(r: TT) -> TD:
            return r.main
        def store(r: TT, s: PluginState[S, D, CC]) -> PluginState[S, D, CC]:
            return s.update_component_data(aff.name, r.comp)
        return wrap, unwrap, store


affiliation_wrapper = dispatch_alg(AffiliationWrapper(), DispatchAffiliation)


def trans_style(handler: FreeTrans) -> Tuple[Boolean, Boolean]:
    tpe = handler.params_spec.rettype
    state_type = (
        Maybe.getattr(tpe, '__args__') / Lists.wrap // _.head
        if tpe is not None and issubclass(tpe, StateT)
        else Nothing
    )
    is_state = lambda st: state_type.exists(lambda t: issubclass(t, st))
    return is_state(PluginState), is_state(Resources)


STR = Tuple[Callable[[PluginState[S, D, CC]], C], Callable[[PluginState[S, D, CC], C], PluginState[S, D, CC]]]


def data_wrapper(handler: FreeTrans, aff: DispatchAffiliation) -> STR:
    explicit_r, explicit_i = handler.resources, handler.internal
    internal, resources = (explicit_i, explicit_r) if (explicit_r or explicit_i) else trans_style(handler)
    def wrap(ps: PluginState[S, D, CC]) -> TD:
        return (
            ps.resources
            if resources else
            ps
            if internal else
            ps.data
        )
    def unwrap(original: PluginState[S, D, CC], result: TD) -> PluginState[S, D, CC]:
        return (
            original.copy(data=result.data)
            if resources else
            result
            if internal else
            original.copy(data=result)
        )
    return wrap, unwrap


def transform_state(
        st: NS[TT, DispatchResult],
        data_wrap: Callable[[PluginState[S, D, CC]], TD],
        affiliation_wrap: AWWrap,
        affiliation_unwrap: AWUnwrap,
        data_unwrap: Callable[[PluginState[S, D, CC], TD], PluginState[S, D, CC]],
        affiliation_store: AWStore,
) -> DRes:
    def get(r: PluginState[S, D, CC]) -> None:
        return affiliation_wrap(r, data_wrap(r))
    def put(r: PluginState[S, D, CC], s: TT) -> None:
        return affiliation_store(s, data_unwrap(r, affiliation_unwrap(s)))
    return plugin_to_dispatch(st.transform_s(get, put))


@do(DRes)
def run_trans(aff: DispatchAffiliation, handler: FreeTrans, args: List[Any]) -> Do:
    aff_wrap, aff_unwrap, aff_store = affiliation_wrapper(aff, handler)
    data_wrap, data_unwrap = data_wrapper(handler, aff)
    yield transform_state(execute_trans(handler), data_wrap, aff_wrap, aff_unwrap, data_unwrap, aff_store)


@do(DRes)
def setup_and_run_trans(trans: Trans, aff: DispatchAffiliation, args: List[Any]) -> Do:
    handler = yield setup_trans(trans, args)
    yield run_trans(aff, handler, args)


def cons_message(tpe: Type[Message], args: List[Any], cmd_name: str, method: str) -> Either[str, Message]:
    validator = ArgValidator(ParamsSpec.from_function(tpe.__init__))
    return Right(tpe(*args)) if validator.validate(len(args)) else Left(validator.error(args, method, cmd_name))


class RunDispatch(Generic[D, NP], Logging):

    def trans(self, dispatch: Trans, aff: DispatchAffiliation) -> DRes:
        return setup_and_run_trans(dispatch, aff, self.args)


class RunDispatchSync(RunDispatch):

    def __init__(self, args: List[Any]) -> None:
        self.args = args


class RunDispatchAsync(RunDispatch):

    def __init__(self, args: List[Any]) -> None:
        self.args = args

    @do(NS[PluginState[S, D, CC], DispatchResult])
    def send_message(self, dispatch: SendMessage, aff: DispatchAffiliation) -> Do:
        cmd_name = yield NS.inspect(__.state.config.vim_cmd_name(dispatch.handler))
        msg_e = cons_message(dispatch.msg, self.args, cmd_name, dispatch.method)
        yield plugin_to_dispatch(msg_e.cata(DispatchResult.error_nio, send_message))


def invalid_dispatch(tpe: Type[RunDispatch], data: Any) -> NvimIO[Any]:
    return NS.failed(f'invalid type passed to `{tpe}`: {data}')


class DispatchJob(Generic[D], Dat['DispatchJob']):

    def __init__(
            self,
            state: PluginStateHolder[D],
            name: str,
            args: List[Any],
            sync: bool,
            bang: Boolean,
    ) -> None:
        self.state = state
        self.name = name
        self.args = args
        self.sync = sync
        self.bang = Boolean(bang)

    @property
    def plugin_name(self) -> str:
        return self.state.state.config.name


__all__ = ('PluginState', 'PluginStateHolder', 'invalid_dispatch', 'DispatchJob')
