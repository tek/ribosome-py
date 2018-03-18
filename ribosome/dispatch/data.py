import abc
from typing import TypeVar, Union, Any, Generic, Type

from amino import List, Boolean, Nil, Maybe, Just, Nothing, IO, Either, Right, Left
from amino.dat import Dat, ADT, DatMeta

from ribosome.request.rpc import RpcHandlerSpec
from ribosome.request.handler.handler import RequestHandler
from ribosome.request.handler.dispatcher import TransDispatcher
from ribosome.request.handler.method import RpcMethod
from ribosome.nvim import NvimIO
from ribosome.nvim.io import NvimIOState
from ribosome.trans.message_base import Message
from ribosome.trans.effects import GatherIOs, GatherSubprocs
from ribosome.trans.action import TransDo, TransLog
from ribosome.trans.handler import FreeTrans

B = TypeVar('B')
Meth = TypeVar('Meth', bound=RpcMethod)
D = TypeVar('D')


class Dispatch:

    def __init__(self, handler: RequestHandler) -> None:
        self.handler = handler

    @property
    def sync(self) -> Boolean:
        return Boolean.isinstance(self, DispatchSync)

    @property
    def async(self) -> Boolean:
        return Boolean.isinstance(self, DispatchAsync)

    @property
    def name(self) -> str:
        return self.handler.name

    def spec(self, name: str, prefix: str) -> RpcHandlerSpec:
        return self.handler.spec(name, prefix)

    @property
    def method(self) -> str:
        return self.handler.method.method


DP = TypeVar('DP', bound=Dispatch)


class DispatchSync(ADT['DispatchSync'], Dispatch, base=True):
    pass


class DispatchAsync(ADT['DispatchAsync'], Dispatch, base=True):
    pass


class SendMessage(DispatchAsync):

    @property
    def desc(self) -> str:
        return f'send `{self.msg.__name__}`'

    @property
    def msg(self) -> Type[Message]:
        return self.handler.dispatcher.msg


class Trans(Generic[Meth, B], DispatchSync, DispatchAsync):

    def __init__(self, handler: RequestHandler[Meth, TransDispatcher[B]]) -> None:
        self.handler = handler

    @property
    def desc(self) -> str:
        return f'trans `{self.name}`'


class DispatchOutput(ADT, base=True): pass


class DispatchError(DispatchOutput):

    @staticmethod
    def cons(problem: Union[str, Exception]) -> 'DispatchError':
        msg = 'fatal error while handling request'
        return (
            DispatchError(msg, Just(problem))
            if isinstance(problem, Exception) else
            DispatchError(problem, Nothing)
        )

    def __init__(self, message: str, exception: Maybe[Exception]) -> None:
        self.message = message
        self.exception = exception

    def _arg_desc(self) -> List[str]:
        return List(self.message)


class DispatchErrors(DispatchOutput):

    def __init__(self, errors: List[DispatchError]) -> None:
        self.errors = errors


class DispatchReturn(DispatchOutput):

    def __init__(self, value: Any) -> None:
        self.value = value

    def _arg_desc(self) -> List[str]:
        return List(self.value)


class DispatchUnit(DispatchOutput):

    def _arg_desc(self) -> List[str]:
        return Nil


class DispatchOutputAggregate(DispatchOutput):

    def __init__(self, results: List['DispatchResult']) -> None:
        self.results = results


class DispatchDo(DispatchOutput):

    def __init__(self, trans: TransDo) -> None:
        self.trans = trans


class DispatchLog(DispatchOutput):

    def __init__(self, trans: TransLog) -> None:
        self.trans = trans


A = TypeVar('A')
R = TypeVar('R')
I = TypeVar('I')


class DIO(Generic[I], ADT['DIO[I]'], base=True):

    @staticmethod
    def cons(io: I) -> Either[str, 'DIO[I]']:
        return (
            Right(IODIO(io))
            if isinstance(io, IO) else
            Right(GatherIOsDIO(io))
            if isinstance(io, GatherIOs) else
            Right(GatherSubprocsDIO(io))
            if isinstance(io, GatherSubprocs) else
            Right(NvimIODIO(io))
            if isinstance(io, NvimIO) else
            Left(f'invalid type for DIO: {io}')
        )

    @abc.abstractproperty
    def handle_result(self) -> FreeTrans:
        ...


class IODIO(Generic[A], DIO[IO[A]]):

    def __init__(self, io: IO[A]) -> None:
        self.io = io

    @property
    def handle_result(self) -> FreeTrans:
        return FreeTrans.id


class GatherIOsDIO(Generic[A], DIO[GatherIOs[A]]):

    def __init__(self, io: GatherIOs[A]) -> None:
        self.io = io

    @property
    def handle_result(self) -> FreeTrans:
        return self.io.handle_result


class GatherSubprocsDIO(Generic[A, R], DIO[GatherSubprocs[A, R]]):

    def __init__(self, io: GatherSubprocs[A, R]) -> None:
        self.io = io

    @property
    def handle_result(self) -> FreeTrans:
        return self.io.handle_result


class NvimIODIO(Generic[A], DIO[NvimIO[A]]):

    def __init__(self, io: NvimIO[A]) -> None:
        self.io = io

    @property
    def handle_result(self) -> FreeTrans:
        return FreeTrans.id


class DispatchIO(Generic[I], DispatchOutput):

    def __init__(self, io: DIO[I]) -> None:
        self.io = io


class DispatchContinuation(ADT['DispatchContinuation'], base=True):
    pass


class DispatchDone(DispatchContinuation):
    pass


class DispatchHandle(DispatchContinuation):
    pass


class DispatchResultMeta(DatMeta):

    @property
    def unit(self) -> 'DispatchResult':
        return DispatchResult(DispatchUnit(), Nil)

    @property
    def unit_nio(self) -> 'NvimIOState[D, DispatchResult]':
        return NvimIOState.pure(DispatchResult.unit)

    def error(self, problem: Union[str, Exception]) -> 'NvimIOState[D, DispatchResult]':
        return DispatchResult(DispatchError.cons(problem), Nil)

    def error_nio(self, problem: Union[str, Exception]) -> 'NvimIOState[D, DispatchResult]':
        return NvimIOState.pure(DispatchResult.error(problem))


class DispatchResult(Dat['DispatchResult'], metaclass=DispatchResultMeta):

    def __init__(self, output: DispatchOutput, msgs: List[Message]) -> None:
        self.output = output
        self.msgs = msgs


__all__ = ('DispatchSync', 'DispatchAsync', 'Legacy', 'SendMessage', 'Trans', 'DispatchOutput',
           'DispatchError', 'DispatchReturn', 'DispatchUnit', 'DispatchContinuation', 'DispatchResult')
