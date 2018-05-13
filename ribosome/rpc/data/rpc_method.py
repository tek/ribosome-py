from amino import ADT


class RpcMethod(ADT['RpcMethod']):
    pass


class CommandMethod(RpcMethod):

    @staticmethod
    def cons(bang: bool=False) -> 'CommandMethod':
        return CommandMethod(bang)

    def __init__(self, bang: bool) -> None:
        self.bang = bang


class FunctionMethod(RpcMethod):

    @property
    def method(self) -> str:
        return 'function'


class AutocmdMethod(RpcMethod):

    @staticmethod
    def cons(pattern: str=None, sync: bool=False) -> 'AutocmdMethod':
        return AutocmdMethod(pattern or '*', sync)

    def __init__(self, pattern: str, sync: bool) -> None:
        self.pattern = pattern
        self.sync = sync


__all__ = ('RpcMethod', 'CommandMethod', 'FunctionMethod', 'AutocmdMethod',)
