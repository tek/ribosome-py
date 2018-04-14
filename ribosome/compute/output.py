from typing import TypeVar, Generic, Any
import logging

from amino import ADT, IO, List, Dat, Nil
from amino.dat import DatMeta
from ribosome.process import Subprocess

A = TypeVar('A')
B = TypeVar('B')
D = TypeVar('D')
P = TypeVar('P')
PIO = TypeVar('PIO')


class ProgOutputInterpreter(Generic[A, B], ADT['ProgOutputInterpreter[A, B]']):
    pass


class ProgOutputUnit(ProgOutputInterpreter[None, None]):
    pass


class ProgOutputResult(Generic[A], ProgOutputInterpreter[A, A]):
    pass


class ProgIOInterpreter(Generic[PIO], ADT['ProgIOInterpreter[PIO]']):
    pass


class ProgScalarIO(ProgIOInterpreter[IO]):
    pass


class ProgGatherIOs(ProgIOInterpreter[List[IO]]):
    pass


class ProgScalarSubprocess(ProgIOInterpreter[Subprocess]):
    pass


class ProgGatherSubprocesses(ProgIOInterpreter[List[Subprocess]]):
    pass


class EchoMeta(DatMeta):

    @property
    def unit(self) -> 'Echo':
        return Echo(Nil, 0)


class Echo(Dat['Echo'], metaclass=EchoMeta):
    info_level = logging.INFO
    error_level = logging.ERROR

    @staticmethod
    def info(msg: str) -> 'Echo':
        return Echo(List(msg), Echo.info_level)

    @staticmethod
    def error(msg: str) -> 'Echo':
        return Echo(List(msg), Echo.error_level)

    def __init__(self, messages: List[str], level: int) -> None:
        self.messages = messages
        self.level = level


class ProgIOEcho(ProgIOInterpreter[None]):
    pass


class ProgIOCustom(ProgIOInterpreter[Any]):
    pass


class ProgOutputIO(Generic[PIO, A], ProgOutputInterpreter[PIO, A]):

    def __init__(self, interpreter: ProgIOInterpreter[PIO]) -> None:
        self.interpreter = interpreter


class GatherIOs(Generic[A], Dat['GatherIOs[A]']):

    def __init__(self, ios: List[IO[A]], timeout: float) -> None:
        self.ios = ios
        self.timeout = timeout


class GatherSubprocesses(Generic[A], Dat['Generic[A]']):

    def __init__(self, subprocs: List[Subprocess[A]], timeout: float) -> None:
        self.subprocs = subprocs
        self.timeout = timeout


__all__ = ('ProgOutputInterpreter', 'ProgOutputUnit', 'ProgOutputResult', 'ProgOutputIO', 'ProgResult', 'ProgReturn',
           'ProgIOInterpreter', 'ProgScalarIO', 'ProgGatherIOs', 'ProgScalarSubprocess', 'ProgGatherSubprocesses',
           'ProgIOCustom', 'ProgOutputIO', 'GatherIOs', 'GatherSubprocesses')
