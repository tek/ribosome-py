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


class ProgOutput(Generic[A, B], ADT['ProgOutput[A, B]']):
    pass


class ProgOutputUnit(ProgOutput[None, None]):
    pass


class ProgOutputResult(Generic[A], ProgOutput[A, A]):
    pass


class ProgIO(Generic[PIO], ADT['ProgIO[PIO]']):
    pass


class ProgScalarIO(ProgIO[IO]):
    pass


class ProgGatherIOs(ProgIO[List[IO]]):
    pass


class ProgScalarSubprocess(ProgIO[Subprocess]):
    pass


class ProgGatherSubprocesses(ProgIO[List[Subprocess]]):
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


class ProgIOEcho(ProgIO[None]):
    pass


class ProgIOCustom(ProgIO[Any]):
    pass


class ProgOutputIO(Generic[PIO, A], ProgOutput[PIO, A]):

    def __init__(self, io: ProgIO[PIO]) -> None:
        self.io = io


class GatherIOs(Generic[A], Dat['GatherIOs[A]']):

    def __init__(self, ios: List[IO[A]], timeout: float) -> None:
        self.ios = ios
        self.timeout = timeout


class GatherSubprocesses(Generic[A], Dat['Generic[A]']):

    def __init__(self, subprocs: List[Subprocess[A]], timeout: float) -> None:
        self.subprocs = subprocs
        self.timeout = timeout


__all__ = ('ProgOutput', 'ProgOutputUnit', 'ProgOutputResult', 'ProgOutputIO', 'ProgResult', 'ProgReturn',
           'ProgIO', 'ProgScalarIO', 'ProgGatherIOs', 'ProgScalarSubprocess', 'ProgGatherSubprocesses',
           'ProgIOCustom', 'ProgOutputIO', 'GatherIOs', 'GatherSubprocesses')
