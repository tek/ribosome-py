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
from ribosome.nvim.io import NvimIOState
from ribosome.trans.message_base import Message
from ribosome.dispatch.transform import AlgResultValidator
from ribosome.trans.send_message import send_message, transform_data_state

# NP = TypeVar('NP', bound=NvimPlugin)
NP = TypeVar('NP')
D = TypeVar('D')
DP = TypeVar('DP', bound=Algebra)
Res = NvimIOState[PluginState[D, NP], DispatchResult]


def run_trans(trans: Trans, args: List[Any]) -> Res:
    handler = trans.handler.dispatcher.handler
    result = handler.run(args)
    validator = AlgResultValidator(trans.name)
    return transform_data_state(validator.validate(result))


def run_internal(trans: Trans, args: List[Any]) -> Res:
    handler = trans.handler.dispatcher.handler
    result = handler.run(args)
    validator = AlgResultValidator(trans.name)
    return validator.validate(result)


def cons_message(tpe: Type[Message], args: List[Any], cmd_name: str, method: str) -> Either[str, Message]:
    validator = ArgValidator(ParamsSpec.from_function(tpe.__init__))
    return Right(tpe(*args)) if validator.validate(args) else Left(validator.error(args, method, cmd_name))


class RunDispatch(Generic[D, NP], Logging):

    def internal(self, dispatch: Internal) -> Res:
        return run_internal(dispatch, self.args)

    def trans(self, dispatch: Trans) -> Res:
        return run_trans(dispatch, self.args)


class RunDispatchSync(RunDispatch):

    def __init__(self, args: List[Any]) -> None:
        self.args = args

    @do(NvimIOState[PluginState[D, NP], DispatchResult])
    def legacy(self, dispatch: Legacy) -> Do:
        plugin = yield NvimIOState.inspect(_.plugin)
        result = dispatch.handler.func(plugin, *self.args)
        yield NvimIOState.pure((DispatchResult(DispatchReturn(result), Nil)))


class RunDispatchAsync(RunDispatch):

    def __init__(self, args: List[Any]) -> None:
        self.args = args

    @do(NvimIOState[PluginState[D, NP], DispatchResult])
    def send_message(self, dispatch: SendMessage) -> Do:
        cmd_name = yield NvimIOState.inspect(__.config.vim_cmd_name(dispatch.handler))
        msg_e = cons_message(dispatch.msg, self.args, cmd_name, dispatch.method)
        yield msg_e.cata(DispatchResult.error_nio, send_message)


def invalid_dispatch(data: Any) -> NvimIO[Any]:
    return NvimIO.failed(f'invalid type passed to `RunDispatch`: {data}')


class DispatchJob(Generic[DP], Dat['DispatchJob']):

    def __init__(
            self,
            dispatches: Map[str, DP],
            state: PluginStateHolder[D, NP],
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
