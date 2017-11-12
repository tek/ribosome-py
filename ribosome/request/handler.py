import abc
from typing import Callable, Type, Generic, Any, TypeVar

from amino import List, Lists, Map, _, Nil, Boolean
from amino.func import flip
from amino.util.string import ToStr, snake_case, camelcase
from amino.algebra import Algebra
from amino.boolean import false
from amino.dat import Dat

from ribosome.rpc import RpcHandlerSpec, RpcCommandSpec, RpcFunctionSpec, RpcAutocommandSpec
from ribosome.machine.message_base import Message
from ribosome.logging import Logging
from ribosome.machine.transition import Handler
from ribosome.data import Data

B = TypeVar('B')
D = TypeVar('D', bound=Data)
M = TypeVar('M', bound=Message)
RHS = TypeVar('RHS', bound=RpcHandlerSpec)


class RequestDispatcher(Algebra, Logging, base=True):

    @abc.abstractproperty
    def args(self) -> List[Any]:
        ...

    @abc.abstractproperty
    def name(self) -> str:
        ...

    @abc.abstractproperty
    def spec_type(self) -> Type[RHS]:
        ...

    @abc.abstractproperty
    def method(self) -> str:
        ...


class MsgDispatcher(Generic[M], RequestDispatcher):

    def __init__(self, msg: Type[M]) -> None:
        self.msg = msg

    def _arg_desc(self) -> List[str]:
        return List(str(self.msg))

    @property
    def args(self) -> List[Any]:
        return List(self.msg)

    @property
    def name(self) -> str:
        return snake_case(self.msg.__name__)


class TransDispatcher(Generic[B], RequestDispatcher):

    def __init__(self, handler: Handler[None, D, B]) -> None:
        self.handler = handler

    @property
    def args(self) -> List[Any]:
        return Nil

    def _arg_desc(self) -> List[str]:
        return List(self.name)

    @property
    def name(self) -> str:
        return self.handler.name


class CmdDispatcher(RequestDispatcher):

    @property
    def spec_type(self) -> Type[RHS]:
        return RpcCommandSpec

    @property
    def method(self) -> str:
        return 'command'


class FunctionDispatcher(RequestDispatcher):

    @property
    def spec_type(self) -> Type[RHS]:
        return RpcFunctionSpec

    @property
    def method(self) -> str:
        return 'function'


class AutocmdDispatcher(RequestDispatcher):

    @property
    def spec_type(self) -> Type[RHS]:
        return RpcAutocommandSpec

    @property
    def method(self) -> str:
        return 'autocmd'


class Cmd(FunctionDispatcher):

    def __init__(self, fun: Callable) -> None:
        self.fun = fun

    def _arg_desc(self) -> List[str]:
        return List()

    @property
    def args(self) -> List[Any]:
        return List()

    @property
    def name(self) -> str:
        return snake_case(self.fun.__name__)


class Fun(FunctionDispatcher):

    def __init__(self, fun: Callable) -> None:
        self.fun = fun

    def _arg_desc(self) -> List[str]:
        return List()

    @property
    def args(self) -> List[Any]:
        return List()

    @property
    def name(self) -> str:
        return snake_case(self.fun.__name__)


class MsgCmd(Generic[M], CmdDispatcher, MsgDispatcher[M]):
    pass


class JsonMsgCmd(Generic[M], CmdDispatcher, MsgDispatcher[M]):
    pass


class MsgFun(Generic[M], FunctionDispatcher, MsgDispatcher[M]):
    pass


class MsgAutocmd(Generic[M], AutocmdDispatcher, MsgDispatcher[M]):
    pass


class CmdTransDispatcher(Generic[B], TransDispatcher[B], CmdDispatcher):
    pass


class FunctionTransDispatcher(Generic[B], TransDispatcher[B], FunctionDispatcher):
    pass


class PrefixStyle(Dat['PrefixStyle']):

    @property
    def short(self) -> Boolean:
        return Boolean.isinstance(self, Short)

    @property
    def full(self) -> Boolean:
        return Boolean.isinstance(self, Full)

    @property
    def plain(self) -> Boolean:
        return Boolean.isinstance(self, Plain)


class Short(PrefixStyle):
    pass


class Full(PrefixStyle):
    pass


class Plain(PrefixStyle):
    pass


DP = TypeVar('DP', bound=RequestDispatcher)


class RequestHandler(Generic[DP], Dat['RequestHandler'], Logging):

    def __init__(
            self,
            dispatcher: DP,
            name: str,
            prefix: PrefixStyle=Short(),
            sync: Boolean=false,
            options: Map[str, Any]=Map(),
    ) -> None:
        self.dispatcher = dispatcher
        self.name = name
        self.prefix = prefix
        self.sync = sync
        self.extra_options = options

    @staticmethod
    def msg_cmd(msg: Type[M]) -> 'RequestHandlerBuilder':
        return RequestHandlerBuilder(MsgCmd(msg))

    @staticmethod
    def msg_fun(msg: Type[M]) -> 'RequestHandlerBuilder':
        return RequestHandlerBuilder(MsgFun(msg))

    @staticmethod
    def msg_autocmd(msg: Type[M]) -> 'RequestHandlerBuilder':
        return RequestHandlerBuilder(MsgAutocmd(msg))

    @staticmethod
    def json_msg_cmd(msg: Type[M]) -> 'RequestHandlerBuilder':
        return RequestHandlerBuilder(JsonMsgCmd(msg))

    @staticmethod
    def trans_cmd(func: Callable[..., B]) -> 'RequestHandlerBuilder':
        return RequestHandlerBuilder(CmdTransDispatcher(func))

    @staticmethod
    def trans_function(func: Callable[..., B]) -> 'RequestHandlerBuilder':
        return RequestHandlerBuilder(FunctionTransDispatcher(func))

    @property
    def options(self) -> Map[str, Any]:
        return self.extra_options ** Map(sync=self.sync)

    @property
    def method(self) -> str:
        return f'{self.dispatcher.method}:{self.name}'

    def vim_cmd_name(self, name: str, prefix: str) -> str:
        pre = name if self.prefix.full else prefix if self.prefix.short else ''
        return f'{camelcase(pre)}{camelcase(self.name)}'

    def spec(self, name: str, prefix: str) -> RpcHandlerSpec:
        return RpcHandlerSpec.cons(self.dispatcher.spec_type, self.sync, self.vim_cmd_name(name, prefix), self.options,
                                   self.method, True)

    @property
    def legacy(self) -> bool:
        return isinstance(self.dispatcher, MsgDispatcher)


class RequestHandlerBuilder(Generic[DP]):

    def __init__(self, dispatcher: DP) -> None:
        self.dispatcher = dispatcher

    def __call__(
            self,
            name: str=None,
            prefix: PrefixStyle=Short(),
            sync: Boolean=false,
            **options: Any
    ) -> RequestHandler:
        name1 = name or self.dispatcher.name
        return RequestHandler(self.dispatcher, name1, prefix, sync, Map(options))


class RequestHandlers(ToStr):

    @staticmethod
    def cons(*handlers: RequestHandler) -> 'RequestHandlers':
        return RequestHandlers(Map(Lists.wrap(handlers).apzip(_.name).map2(flip)))

    def __init__(self, handlers: Map[str, RequestHandler]) -> None:
        self.handlers = handlers

    def _arg_desc(self) -> List[str]:
        return List(str(self.handlers))


__all__ = ('RequestDispatcher', 'MsgDispatcher', 'TransDispatcher', 'CmdDispatcher', 'FunctionDispatcher',
           'AutocmdDispatcher', 'PrefixStyle', 'Short', 'Full', 'Plain', 'RequestHandler', 'RequestHandlers')
