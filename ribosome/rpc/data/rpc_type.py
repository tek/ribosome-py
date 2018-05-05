from amino import ADT


class RpcType(ADT['RpcType']):
    pass


class BlockingRpc(RpcType):

    def __init__(self, id: int) -> None:
        self.id = id


class NonblockingRpc(RpcType):
    pass


__all__ = ('RpcType', 'BlockingRpc', 'NonblockingRpc',)
