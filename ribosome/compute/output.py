from typing import TypeVar, Generic, Any

from amino import ADT, IO, List, Dat
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
