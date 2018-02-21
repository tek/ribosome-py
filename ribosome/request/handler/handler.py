from typing import Callable, Type, Generic, Any, TypeVar, Tuple

from amino import List, Lists, Map, _, Boolean, __, Maybe, Nothing
from amino.func import flip
from amino.util.string import ToStr, camelcase
from amino.dat import ADT
from amino.boolean import false
from amino.state import StateT

from ribosome.request.rpc import RpcHandlerSpec
from ribosome.logging import Logging
from ribosome.request.handler.dispatcher import RequestDispatcher, MsgDispatcher, TransDispatcher
from ribosome.request.handler.prefix import PrefixStyle, Short
from ribosome.request.handler.method import RpcMethod, CmdMethod, FunctionMethod, AutocmdMethod
from ribosome.trans.message_base import Message
from ribosome.request.handler.arg_parser import ArgParser, JsonArgParser, TokenArgParser
from ribosome.request.args import ParamsSpec
from ribosome.trans.handler import FreeTrans

B = TypeVar('B')
D = TypeVar('D')
M = TypeVar('M', bound=Message)
RHS = TypeVar('RHS', bound=RpcHandlerSpec)
DP = TypeVar('DP', bound=RequestDispatcher)
Meth = TypeVar('Meth', bound=RpcMethod)


class RequestHandler(Generic[Meth, DP], ADT['RequestHandler'], Logging):

    def __init__(
            self,
            method: Meth,
            dispatcher: DP,
            name: str,
            prefix: PrefixStyle,
            sync: Boolean,
            json: Boolean,
            extra_options: Map[str, Any],
    ) -> None:
        self.method = method
        self.dispatcher = dispatcher
        self.name = name
        self.prefix = prefix
        self.sync = sync
        self.json = json
        self.extra_options = extra_options

    @staticmethod
    def msg_cmd(msg: Type[M]) -> 'RequestHandlerBuilder':
        return RequestHandlerBuilder(CmdMethod(), MsgDispatcher(msg))

    @staticmethod
    def msg_fun(msg: Type[M]) -> 'RequestHandlerBuilder':
        return RequestHandlerBuilder(FunctionMethod(), MsgDispatcher(msg))

    @staticmethod
    def msg_function(msg: Type[M]) -> 'RequestHandlerBuilder':
        return RequestHandlerBuilder(FunctionMethod(), MsgDispatcher(msg))

    @staticmethod
    def msg_autocmd(msg: Type[M]) -> 'RequestHandlerBuilder':
        return RequestHandlerBuilder(AutocmdMethod(), MsgDispatcher(msg))

    @staticmethod
    def trans_cmd(func: Callable[..., B]) -> 'RequestHandlerBuilder':
        return RequestHandlerBuilder(CmdMethod(), TransDispatcher(func))

    @staticmethod
    def trans_function(func: Callable[..., B]) -> 'RequestHandlerBuilder':
        return RequestHandlerBuilder(FunctionMethod(), TransDispatcher(func))

    @staticmethod
    def trans_autocmd(func: Callable[..., B]) -> 'RequestHandlerBuilder':
        return RequestHandlerBuilder(AutocmdMethod(), TransDispatcher(func))

    @property
    def allow_sync(self) -> Boolean:
        return self.dispatcher.allow_sync

    @property
    def options(self) -> Map[str, Any]:
        return self.extra_options ** Map(sync=self.sync) ** self.dispatcher.rpc_options

    @property
    def method_str(self) -> str:
        return f'{self.method.method}:{self.name}'

    def vim_cmd_name(self, name: str, prefix: str) -> str:
        pre = name if self.prefix.full else prefix if self.prefix.short else ''
        return f'{camelcase(pre)}{camelcase(self.name)}'

    def spec(self, name: str, prefix: str) -> RpcHandlerSpec:
        return RpcHandlerSpec.cons(self.method.spec_type, self.sync, self.vim_cmd_name(name, prefix), self.options,
                                   self.method_str, True)

    @property
    def legacy(self) -> bool:
        return isinstance(self.dispatcher, MsgDispatcher)

    def parser(self, params_spec: ParamsSpec) -> ArgParser:
        tpe = JsonArgParser if self.json else TokenArgParser
        return tpe(params_spec)

    @property
    def msg(self) -> Boolean:
        return self.dispatcher.is_msg


class RequestHandlerBuilder(Generic[Meth, DP]):

    def __init__(self, method: Meth, dispatcher: DP) -> None:
        self.method = method
        self.dispatcher = dispatcher

    @property
    def sync_default(self) -> Boolean:
        return Boolean.isinstance(self.method, FunctionMethod)

    def __call__(
            self,
            name: str=None,
            prefix: PrefixStyle=Short(),
            sync: Boolean=None,
            json: Boolean=false,
            **options: Any,
    ) -> RequestHandler:
        name1 = name or self.dispatcher.name
        sync1 = self.sync_default if sync is None else sync
        return RequestHandler(
            self.method,
            self.dispatcher,
            name1,
            prefix,
            sync1,
            json,
            Map(options),
        )


class RequestHandlers(ToStr):

    @staticmethod
    def cons(*handlers: RequestHandler) -> 'RequestHandlers':
        return RequestHandlers(Map(Lists.wrap(handlers).apzip(_.name).map2(flip)))

    def __init__(self, handlers: Map[str, RequestHandler]) -> None:
        self.handlers = handlers

    def _arg_desc(self) -> List[str]:
        return List(str(self.handlers))

    def rpc_specs(self, name: str, prefix: str) -> List[RpcHandlerSpec]:
        return self.handlers.v / __.spec(name, prefix)

    @property
    def trans_handlers(self) -> List[FreeTrans]:
        return (
            self.handlers
            .v
            .map(_.dispatcher)
            .filter_type(TransDispatcher)
            .map(_.handler)
        )


__all__ = ('RequestHandler', 'RequestHandlers')
