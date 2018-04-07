from typing import Generic, TypeVar

from amino import ADT

from ribosome.nvim.io.state import NS

A = TypeVar('A')
D = TypeVar('D')


class Compilation(Generic[D, A], ADT['Compilation']):
    pass


class CompilationSuccess(Generic[D, A], Compilation[D, A]):

    def __init__(self, prog: NS[D, A]) -> None:
        self.prog = prog


class CompilationFailure(Generic[D, A], Compilation[D, A]):

    def __init__(self, error: str) -> None:
        self.error = error


__all__ = ('Compilation', 'CompilationSuccess', 'CompilationFailure')
