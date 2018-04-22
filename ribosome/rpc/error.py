from amino import ADT


class RpcReadError(ADT['RpcReadError']):
    pass


class RpcProcessExit(RpcReadError):
    pass


class RpcReadErrorUnknown(RpcReadError):

    def __init__(self, message: str) -> None:
        self.message = message


__all__ = ('RpcReadError', 'RpcProcessExit', 'RpcReadErrorUnknown')
