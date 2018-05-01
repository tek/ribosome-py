import abc

from amino.dat import ADT


class RpcMethod(ADT['RpcMethod']):

    @abc.abstractproperty
    def method(self) -> str:
        ...


class CommandMethod(RpcMethod):

    @staticmethod
    def cons(bang: bool=False) -> 'CommandMethod':
        return CommandMethod(bang)

    def __init__(self, bang: bool) -> None:
        self.bang = bang

    @property
    def method(self) -> str:
        return 'command'


class FunctionMethod(RpcMethod):

    @property
    def method(self) -> str:
        return 'function'


class AutocmdMethod(RpcMethod):

    @staticmethod
    def cons(pattern: str='*') -> 'AutocmdMethod':
        return AutocmdMethod(pattern)

    def __init__(self, pattern: str) -> None:
        self.pattern = pattern

    @property
    def method(self) -> str:
        return 'autocmd'


__all__ = ('RpcMethod', 'CommandMethod', 'FunctionMethod', 'AutocmdMethod',)
