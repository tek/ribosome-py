from typing import TypeVar, Any, Generic, Type, Callable

from amino import List, Boolean, Nil, Either, Left, Right, __, _, L
from amino.dat import Dat
from amino.do import do, Do
from amino.dispatch import dispatch_alg

from ribosome.nvim import NvimIO
from ribosome.logging import Logging
from ribosome.request.args import ArgValidator, ParamsSpec
from ribosome.plugin_state import PluginState, PluginStateHolder, DispatchAffiliaton, RootDispatch, ComponentDispatch
from ribosome.dispatch.data import (DispatchReturn, Internal, Trans, SendMessage, DispatchResult, Dispatch,
                                    ResourcesState)
from ribosome.nvim.io import NS
from ribosome.trans.message_base import Message
from ribosome.dispatch.transform import validate_trans_complete
from ribosome.trans.send_message import send_message, transform_data_state
from ribosome.trans.handler import FreeTransHandler
from ribosome.dispatch.component import ComponentData
from ribosome.request.handler.handler import RequestHandler
from ribosome.request.handler.dispatcher import RequestDispatcher
from ribosome.config.settings import Settings
from ribosome.config.config import Resources

NP = TypeVar('NP')
D = TypeVar('D')
DP = TypeVar('DP', bound=Dispatch)
S = TypeVar('S', bound=Settings)
Res = NS[PluginState[S, D], DispatchResult]
St = TypeVar('St')
C = TypeVar('C')
DST = Callable[[NS[St, C]], NS[PluginState[St, D], C]]


def log_trans(trans: FreeTransHandler) -> NS[PluginState[S, D], None]:
    return NS.pure(None) if trans.name in ('trans_log', 'pure') else NS.modify(__.log_trans(trans.name))


def execute_trans(handler: FreeTransHandler) -> NS[D, DispatchResult]:
    return validate_trans_complete(handler.run())


class DataStateTransformer:

    def root_dispatch(self, aff: RootDispatch[DP]) -> DST:
        return transform_data_state

    def component_dispatch(self, aff: ComponentDispatch[DP]) -> DST:
        def get(r: PluginState[S, D]) -> ComponentData[D, C]:
            return ComponentData(r.data, r.component_data.lift(aff.name).get_or_else(aff.state_ctor()))
        def put(r: PluginState[S, D], s: ComponentData[D, C]) -> PluginState[S, D]:
            return r.update_component_data(aff.name, s.comp).copy(data=s.main)
        def transform(st: NS[St, C]) -> NS[PluginState[S, D], C]:
            return st.transform_s(get, put)
        return transform


data_state_transformer = dispatch_alg(DataStateTransformer(), DispatchAffiliaton)


def parse_args(handler: RequestHandler, dispatcher: RequestDispatcher, args: List[Any]) -> NS[D, List[Any]]:
    return handler.parser(dispatcher.params_spec).parse(args)


@do(Res)
def setup_trans(aff: DispatchAffiliaton[Dispatch], args: List[Any]) -> Do:
    trans = aff.dispatch
    dispatcher = trans.handler.dispatcher
    parsed_args = yield NS.from_either(parse_args(trans.handler, dispatcher, args))
    yield log_trans(trans)
    yield NS.pure(dispatcher.handler(*parsed_args))


@do(Res)
def run_trans(aff: DispatchAffiliaton[Trans], args: List[Any]) -> Do:
    handler = yield setup_trans(aff, args)
    trans_state = data_state_transformer(aff)
    yield trans_state(execute_trans(handler))


@do(Res)
def run_internal(aff: DispatchAffiliaton[Internal], args: List[Any]) -> Do:
    handler = yield setup_trans(aff, args)
    yield execute_trans(handler)


def trans_resources_state(settings: S, st: NS[Resources[S, St], C]) -> NS[St, C]:
    return st.transform_s(L(Resources)(settings, _), lambda r, s: s.data)


@do(Res)
def run_resources(aff: DispatchAffiliaton[ResourcesState], args: List[Any]) -> Do:
    handler = yield setup_trans(aff, args)
    trans_state = data_state_transformer(aff)
    settings = yield NS.inspect(_.settings)
    yield trans_state(trans_resources_state(settings, execute_trans(handler)))


def cons_message(tpe: Type[Message], args: List[Any], cmd_name: str, method: str) -> Either[str, Message]:
    validator = ArgValidator(ParamsSpec.from_function(tpe.__init__))
    return Right(tpe(*args)) if validator.validate(len(args)) else Left(validator.error(args, method, cmd_name))


class RunDispatch(Generic[D, NP], Logging):

    def internal(self, dispatch: Internal, aff: DispatchAffiliaton[Internal]) -> Res:
        return run_internal(aff, self.args)

    def trans(self, dispatch: Trans, aff: DispatchAffiliaton[Trans]) -> Res:
        return run_trans(aff, self.args)

    def resources_state(self, dispatch: ResourcesState, aff: DispatchAffiliaton[ResourcesState]) -> Res:
        return run_resources(aff, self.args)


class RunDispatchSync(RunDispatch):

    def __init__(self, args: List[Any]) -> None:
        self.args = args


class RunDispatchAsync(RunDispatch):

    def __init__(self, args: List[Any]) -> None:
        self.args = args

    @do(NS[PluginState[S, D], DispatchResult])
    def send_message(self, dispatch: SendMessage, aff: DispatchAffiliaton[SendMessage]) -> Do:
        cmd_name = yield NS.inspect(__.config.vim_cmd_name(dispatch.handler))
        msg_e = cons_message(dispatch.msg, self.args, cmd_name, dispatch.method)
        yield msg_e.cata(DispatchResult.error_nio, send_message)


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
