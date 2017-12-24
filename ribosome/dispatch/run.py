from typing import TypeVar, Any, Generic, Type

from amino import Map, List, Boolean, Nil, Either, Left, Right, __, _
from amino.dat import Dat
from amino.algebra import Algebra
from amino.do import do, Do

from ribosome.nvim import NvimIO
from ribosome.logging import Logging
from ribosome.request.args import ArgValidator, ParamsSpec
from ribosome.plugin_state import PluginState, PluginStateHolder
from ribosome.dispatch.data import Legacy, DispatchReturn, Internal, Trans, SendMessage, DispatchResult
from ribosome.nvim.io import NS
from ribosome.trans.message_base import Message
from ribosome.dispatch.transform import validate_trans_complete
from ribosome.trans.send_message import send_message, transform_data_state
from ribosome.trans.handler import FreeTransHandler

NP = TypeVar('NP')
D = TypeVar('D')
DP = TypeVar('DP', bound=Algebra)
Res = NS[PluginState[D], DispatchResult]


def log_trans(trans: FreeTransHandler) -> NS[PluginState[D], None]:
    return NS.pure(None) if trans.name in ('trans_log', 'pure') else NS.modify(__.log_trans(trans.name))


def execute_trans(handler: FreeTransHandler) -> NS[D, DispatchResult]:
    return validate_trans_complete(handler.run())


def execute_data_trans(handler: FreeTransHandler) -> Res:
    return transform_data_state(execute_trans(handler))


@do(Res)
def run_trans(trans: Trans, args: List[Any]) -> Do:
    dispatcher = trans.handler.dispatcher
    handler = dispatcher.handler
    parsed_args = yield NS.from_either(trans.handler.parser(dispatcher.params_spec).parse(args))
    yield log_trans(trans)
    yield execute_data_trans(handler(*parsed_args))


@do(Res)
def run_internal(trans: Trans, args: List[Any]) -> Do:
    handler = trans.handler.dispatcher.handler(*args)
    yield log_trans(trans)
    yield execute_trans(handler)


def cons_message(tpe: Type[Message], args: List[Any], cmd_name: str, method: str) -> Either[str, Message]:
    validator = ArgValidator(ParamsSpec.from_function(tpe.__init__))
    return Right(tpe(*args)) if validator.validate(len(args)) else Left(validator.error(args, method, cmd_name))


class RunDispatch(Generic[D, NP], Logging):

    def internal(self, dispatch: Internal) -> Res:
        return run_internal(dispatch, self.args)

    def trans(self, dispatch: Trans) -> Res:
        return run_trans(dispatch, self.args)


class RunDispatchSync(RunDispatch):

    def __init__(self, args: List[Any]) -> None:
        self.args = args

    @do(NS[PluginState[D], DispatchResult])
    def legacy(self, dispatch: Legacy) -> Do:
        plugin = yield NS.inspect(_.plugin)
        result = dispatch.handler.func(plugin, *self.args)
        yield NS.pure((DispatchResult(DispatchReturn(result), Nil)))


class RunDispatchAsync(RunDispatch):

    def __init__(self, args: List[Any]) -> None:
        self.args = args

    @do(NS[PluginState[D], DispatchResult])
    def send_message(self, dispatch: SendMessage) -> Do:
        cmd_name = yield NS.inspect(__.config.vim_cmd_name(dispatch.handler))
        msg_e = cons_message(dispatch.msg, self.args, cmd_name, dispatch.method)
        yield msg_e.cata(DispatchResult.error_nio, send_message)


def invalid_dispatch(data: Any) -> NvimIO[Any]:
    return NvimIO.failed(f'invalid type passed to `RunDispatch`: {data}')


class DispatchJob(Generic[DP], Dat['DispatchJob']):

    def __init__(
            self,
            dispatches: Map[str, DP],
            state: PluginStateHolder[D],
            name: str,
            args: List[Any],
            sync: bool,
            plugin_name: str,
            bang: Boolean,
    ) -> None:
        self.dispatches = dispatches
        self.state = state
        self.name = name
        self.args = args
        self.sync = sync
        self.plugin_name = plugin_name
        self.bang = Boolean(bang)


__all__ = ('PluginState', 'PluginStateHolder', 'invalid_dispatch', 'DispatchJob')
