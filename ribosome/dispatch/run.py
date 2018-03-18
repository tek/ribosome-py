import abc
from typing import TypeVar, Any, Generic, Type, Callable, Tuple, Union

from amino import List, Boolean, Either, Left, Right, __, Maybe, Lists, Nothing, _, ADT, L
from amino.dat import Dat
from amino.do import do, Do
from amino.dispatch import dispatch_alg, PatMat
from amino.state import StateT
from amino.lenses.lens import lens

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

A = TypeVar('A')
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
# FIXME affiliation_wrapper and plugin_state_wrapper must be swapped
class affiliation_wrapper(PatMat, alg=DispatchAffiliation):

    def __init__(self, handler: FreeTrans) -> None:
        self.handler = handler

    def root_dispatch(self, aff: RootDispatch) -> AWR:
        return self._root_dispatch()

    def _root_dispatch(self) -> AWR:
        def wrap(r: PluginState[S, D, CC], b: TD) -> TT:
            return b
        def unwrap(r: TT) -> TD:
            return r
        def store(r: TT, s: PluginState[S, D, CC]) -> PluginState[S, D, CC]:
            return s
        return wrap, unwrap, store

    def component_dispatch(self, aff: ComponentDispatch) -> AWR:
        return (
            self._component_dispatch(aff)
            if self.handler.component else
            self._root_dispatch()
        )

    def _component_dispatch(self, aff: ComponentDispatch) -> AWR:
        def wrap(original: PluginState[S, D, CC], wrapped: TD) -> TT:
            return ComponentData(wrapped, original.data_for(aff.component))
        def unwrap(r: TT) -> TD:
            return r.main
        def store(r: TT, s: PluginState[S, D, CC]) -> PluginState[S, D, CC]:
            return s.update_component_data(aff.name, r.comp)
        return wrap, unwrap, store


# FIXME also descend into `ComponentData`
def handler_has_state(handler: FreeTrans, tpe: type) -> Boolean:
    return handler.params_spec.state_type.exists(L(issubclass)(_, tpe))


STR = Tuple[Callable[[PluginState[S, D, CC]], C], Callable[[PluginState[S, D, CC], C], PluginState[S, D, CC]]]


def plugin_state_wrapper(handler: FreeTrans, aff: DispatchAffiliation) -> STR:
    explicit_r, explicit_i = handler.resources, handler.internal
    internal = explicit_i if explicit_i else handler_has_state(handler, PluginState)
    def wrap(ps: PluginState[S, D, CC]) -> TD:
        return (
            ps
            if internal else
            ps.data
        )
    def unwrap(original: PluginState[S, D, CC], result: TD) -> PluginState[S, D, CC]:
        return (
            result
            if internal else
            original.copy(data=result)
        )
    return wrap, unwrap


# FIXME parameterize `FreeTrans` by state type to replace `Any` here
class ResourcesWrapping(Generic[S, C, CC, A], ADT['ResourcesWrapped[S, C, CC]']):

    def __init__(self, data: A) -> None:
        self.data = data


class ResourcesWrapped(Generic[S, C, CC, A], ResourcesWrapping[S, C, CC, Resources[S, C, CC]]):
    pass


class ResourcesPlain(Generic[S, C, CC, A], ResourcesWrapping[S, C, CC, C]):
    pass


RWWrap = Callable[[C], ResourcesWrapping[S, C, CC, A]]
RWUnwrap = Callable[[ResourcesWrapping[S, C, CC, A]], C]


class unwrap_resources(PatMat, alg=ResourcesWrapping):

    def resources_wrapped(self, rw: ResourcesWrapped[S, C, CC, A]) -> C:
        return rw.data.data

    def resources_plain(self, rw: ResourcesPlain[S, C, CC, A]) -> C:
        return rw.data


def resources_wrapper(handler: FreeTrans) -> Tuple[RWWrap, RWUnwrap]:
    def wrap(ps: PluginState[S, D, CC], data: C) -> ResourcesWrapping[S, C, CC, A]:
        return (
            ResourcesWrapped(ps.resources_with(data))
            if handler.resources or handler_has_state(handler, Resources) else
            ResourcesPlain(data)
        )
    return wrap, unwrap_resources.match



def transform_state(
        st: NS[TT, DispatchResult],
        plugin_state_wrap: Callable[[PluginState[S, D, CC]], TD],
        affiliation_wrap: AWWrap,
        resources_wrap: RWWrap,
        affiliation_unwrap: AWUnwrap,
        plugin_state_unwrap: Callable[[PluginState[S, D, CC], TD], PluginState[S, D, CC]],
        resources_unwrap: RWUnwrap,
        affiliation_store: AWStore,
) -> DRes:
    def get(r: PluginState[S, D, CC]) -> None:
        return resources_wrap(r, affiliation_wrap(r, plugin_state_wrap(r)))
    def put(r: PluginState[S, D, CC], s: TT) -> None:
        data = resources_unwrap(s)
        return affiliation_store(data, plugin_state_unwrap(r, affiliation_unwrap(data)))
    return plugin_to_dispatch(st.zoom(lens.data).transform_s(get, put))


@do(DRes)
def run_trans(aff: DispatchAffiliation, handler: FreeTrans, args: List[Any]) -> Do:
    aff_wrap, aff_unwrap, aff_store = affiliation_wrapper(handler)(aff)
    plugin_state_wrap, plugin_state_unwrap = plugin_state_wrapper(handler, aff)
    resources_wrap, resources_unwrap = resources_wrapper(handler)
    yield transform_state(
        execute_trans(handler),
        plugin_state_wrap,
        aff_wrap,
        resources_wrap,
        aff_unwrap,
        plugin_state_unwrap,
        resources_unwrap,
        aff_store,
    )


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
