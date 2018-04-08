import abc
from typing import TypeVar, Union, Any, Generic

from amino import List, Boolean, Nil, Maybe, Just, Nothing, IO, Either, Right, Left
from amino.dat import Dat, ADT, DatMeta

from ribosome.request.handler.method import RpcMethod
from ribosome.nvim.io.compute import NvimIO
# from ribosome.trans.action import TransDo, TransLog
# from ribosome.compute.prog import Program
from ribosome.trans.recursive_effects import GatherIOs, GatherSubprocs

B = TypeVar('B')
Meth = TypeVar('Meth', bound=RpcMethod)
D = TypeVar('D')


class DispatchOutput(ADT['DispatchOutput']): pass


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


# class DispatchDo(DispatchOutput):

#     def __init__(self, trans: TransDo) -> None:
#         self.trans = trans


# class DispatchLog(DispatchOutput):

#     def __init__(self, trans: TransLog) -> None:
#         self.trans = trans


A = TypeVar('A')
R = TypeVar('R')
I = TypeVar('I')


# class DIO(Generic[I], ADT['DIO[I]']):

#     @staticmethod
#     def cons(io: I) -> Either[str, 'DIO[I]']:
#         return (
#             Right(IODIO(io))
#             if isinstance(io, IO) else
#             Right(GatherIOsDIO(io))
#             if isinstance(io, GatherIOs) else
#             Right(GatherSubprocsDIO(io))
#             if isinstance(io, GatherSubprocs) else
#             Right(NvimIODIO(io))
#             if isinstance(io, NvimIO) else
#             Left(f'invalid type for DIO: {io}')
#         )

#     @abc.abstractproperty
#     def handle_result(self) -> Program:
#         ...


# class IODIO(Generic[A], DIO[IO[A]]):

#     def __init__(self, io: IO[A]) -> None:
#         self.io = io

#     @property
#     def handle_result(self) -> Program:
#         return Program.id


# class GatherIOsDIO(Generic[A], DIO[GatherIOs[A]]):

#     def __init__(self, io: GatherIOs[A]) -> None:
#         self.io = io

#     @property
#     def handle_result(self) -> Program:
#         return self.io.handle_result


# class GatherSubprocsDIO(Generic[A, R], DIO[GatherSubprocs[A, R]]):

#     def __init__(self, io: GatherSubprocs[A, R]) -> None:
#         self.io = io

#     @property
#     def handle_result(self) -> Program:
#         return self.io.handle_result


# class NvimIODIO(Generic[A], DIO[NvimIO[A]]):

#     def __init__(self, io: NvimIO[A]) -> None:
#         self.io = io

#     @property
#     def handle_result(self) -> Program:
#         return Program.id


class DispatchIO(Generic[I], DispatchOutput):
    pass

    # def __init__(self, io: DIO[I]) -> None:
    #     self.io = io


class DispatchContinuation(ADT['DispatchContinuation']):
    pass


class DispatchDone(DispatchContinuation):
    pass


class DispatchHandle(DispatchContinuation):
    pass


__all__ = ('DispatchSync', 'DispatchAsync', 'Legacy', 'SendMessage', 'TransDispatch', 'DispatchOutput',
           'DispatchError', 'DispatchReturn', 'DispatchUnit', 'DispatchContinuation')
