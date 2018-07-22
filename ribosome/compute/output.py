from typing import TypeVar, Generic, Any
import logging

from amino import ADT, IO, List, Dat, Nil
from amino.dat import DatMeta
from ribosome.process import Subprocess, SubprocessResult

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


class GatherItem(Generic[A], ADT['GatherItem[A]']):
    pass


class GatherIO(GatherItem[A]):

    def __init__(self, io: IO[A]) -> None:
        self.io = io


class GatherSubprocess(GatherItem[A]):

    def __init__(self, subprocess: Subprocess[A]) -> None:
        self.subprocess = subprocess


class GatherResult(Generic[A], ADT['GatherResult[A]']):
    pass


class GatherIOResult(Generic[A], GatherResult[A]):

    def __init__(self, result: A) -> None:
        self.result = result


class GatherSubprocessResult(Generic[A], GatherResult[A]):

    def __init__(self, result: SubprocessResult[A]) -> None:
        self.result = result


class ProgGather(ProgIO[List[GatherItem]]):
    pass


class EchoMeta(DatMeta):

    @property
    def unit(self) -> 'Echo':
        return Echo(Nil, 0)


class Echo(Dat['Echo'], metaclass=EchoMeta):
    info_level = logging.INFO
    error_level = logging.ERROR
    debug_level = logging.DEBUG

    @staticmethod
    def info(msg: str) -> 'Echo':
        return Echo(List(msg), Echo.info_level)

    @staticmethod
    def error(msg: str) -> 'Echo':
        return Echo(List(msg), Echo.error_level)

    @staticmethod
    def debug(msg: str) -> 'Echo':
        return Echo(List(msg), Echo.debug_level)

    @staticmethod
    def debugs(msg: List[str]) -> 'Echo':
        return Echo(msg, Echo.debug_level)

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


class GatherSubprocesses(Generic[A], Dat['GatherSubprocess[A]']):

    def __init__(self, subprocs: List[Subprocess[A]], timeout: float) -> None:
        self.subprocs = subprocs
        self.timeout = timeout


class Gather(Generic[A], Dat['Gather[A]']):

    def __init__(self, items: List[GatherItem[A]], timeout: float) -> None:
        self.items = items
        self.timeout = timeout


__all__ = ('ProgOutput', 'ProgOutputUnit', 'ProgOutputResult', 'ProgOutputIO', 'ProgResult', 'ProgReturn',
           'ProgIO', 'ProgScalarIO', 'ProgGatherIOs', 'ProgScalarSubprocess', 'ProgGatherSubprocesses',
           'ProgIOCustom', 'ProgOutputIO', 'GatherIOs', 'GatherSubprocesses', 'GatherItem', 'GatherIO',
           'GatherSubprocess', 'ProgGather', 'Gather', 'GatherResult', 'GatherIOResult', 'GatherSubprocessResult',)
