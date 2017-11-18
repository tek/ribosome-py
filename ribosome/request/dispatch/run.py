from typing import TypeVar, Any, Generic, Tuple, Type, Union, Generator

from amino import Map, List, Boolean, Nil, Either, Left, Right, _, __, __
from amino.dat import Dat
from amino.algebra import Algebra
from amino.do import do

from ribosome.nvim import NvimIO
from ribosome.logging import Logging
from ribosome.machine.message_base import Message
from ribosome.machine.handler import AlgResultValidator
from ribosome.machine.transition import TransitionLog
from ribosome.request.args import ArgValidator, ParamsSpec
from ribosome.machine.send_message import send_message
from ribosome.plugin_state import PluginState, PluginStateHolder
from ribosome.request.dispatch.data import (DispatchOutput, Legacy, DispatchReturn, Internal, Trans, DispatchUnit,
                                            DispatchError, SendMessage, DispatchResult, DispatchDone)
from ribosome.nvim.io import NvimIOState

# NP = TypeVar('NP', bound=NvimPlugin)
NP = TypeVar('NP')
D = TypeVar('D')
DP = TypeVar('DP', bound=Algebra)
DispatchResult1 = Tuple[DispatchOutput, PluginState[D, NP], List[Message]]


def handle_trans(trans: Trans, state: PluginState[D, NP], args: List[Any]) -> DispatchResult:
    handler = trans.handler.dispatcher.handler
    msg = handler.message(*args)
    result = handler.execute(None, state.data, msg)
    validator = AlgResultValidator(trans.name)
    trans_result = validator.validate(result, state.data)
    return DispatchUnit(), state.log_message(msg).update(trans_result.data), trans_result.resend + trans_result.pub


def handle_internal(trans: Trans, state: PluginState[D, NP], args: List[Any]) -> DispatchResult1:
    handler = trans.handler.dispatcher.handler
    result = handler.execute(None, state, args)
    validator = AlgResultValidator(trans.name)
    trans_result = validator.validate(result, state.data)
    return trans_result.output / DispatchReturn | DispatchUnit, state, Nil


def cons_message(tpe: Type[Message], args: List[Any], cmd_name: str, method: str) -> Either[str, Message]:
    validator = ArgValidator(ParamsSpec.from_function(tpe.__init__))
    return Right(tpe(*args)) if validator.validate(args) else Left(validator.error(args, method, cmd_name))


class RunDispatchSync(Generic[D, NP], Logging):

    def __init__(self, args: List[Any]) -> None:
        self.args = args

    @do(NvimIOState[PluginState[D, NP], DispatchResult])
    def legacy(self, dispatch: Legacy) -> Generator:
        state = yield NvimIOState.get()
        root = state.root
        root.state = state.data
        result = dispatch.handler.func(state.plugin, *self.args)
        new_state = state.update(root.state).log_messages(root.last_message_log)
        yield NvimIOState.set(new_state)
        yield NvimIOState.pure((DispatchResult(DispatchReturn(result), Nil)))

    def internal(self, dispatch: Internal) -> NvimIO[DispatchResult1]:
        return NvimIO(lambda v: handle_internal(dispatch, self.state, self.args))

    def trans(self, dispatch: Trans) -> NvimIO[DispatchResult1]:
        return NvimIO(lambda v: handle_trans(dispatch, self.state, self.args))


class RunDispatchAsync(Generic[D, NP], Logging):

    def __init__(self, args: List[Any]) -> None:
        self.args = args

    # sending messages cannot produce return values to vim, ever, because we want to support multiple components.
    # therefore, we can accumulate the results of the components by aggregating errors and messages.
    @do(NvimIOState[PluginState[D, NP], DispatchResult])
    def send_message(self, dispatch: SendMessage) -> Generator:
        handler = dispatch.handler
        dispatcher = handler.dispatcher
        method = handler.method
        config = yield NvimIOState.inspect(_.config)
        name = config.name
        prefix = config.prefix
        msg_e = cons_message(dispatcher.msg, self.args, handler.vim_cmd_name(name, prefix), method.method)
        def error(problem: Union[str, Exception]) -> NvimIOState[PluginState[D, NP], DispatchResult]:
            return NvimIOState.pure(DispatchResult(DispatchError.cons(problem), Nil))
        @do(NvimIOState[PluginState[D, NP], DispatchResult])
        def send(msg: Message) -> Generator:
            log, result = yield send_message(msg)
            yield NvimIOState.modify(__.update(result.data))
            yield NvimIOState.modify(__.log(log))
            yield NvimIOState.pure(DispatchResult(DispatchUnit(), result.pub + result.resend))
        yield msg_e.cata(error, send)

    def internal(self, dispatch: Internal) -> NvimIO[DispatchResult1]:
        return NvimIO(lambda v: handle_internal(dispatch, self.state, self.args))

    def trans(self, dispatch: Trans) -> NvimIO[DispatchResult1]:
        return NvimIO(lambda v: handle_trans(dispatch, self.state, self.args))


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
