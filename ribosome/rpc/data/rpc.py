from typing import Any

from amino import Dat, List, Nil

from ribosome.rpc.data.rpc_type import NonblockingRpc, RpcType, BlockingRpc


class Rpc(Dat['Rpc']):

    @staticmethod
    def nonblocking(method: str, args: List[Any]) -> 'Rpc':
        return Rpc(method, args, NonblockingRpc())

    def __init__(self, method: str, args: List[Any], tpe: RpcType) -> None:
        self.method = method
        self.args = args
        self.tpe = tpe

    @property
    def sync(self) -> bool:
        return isinstance(self.tpe, BlockingRpc)


class ActiveRpc(Dat['ActiveRpc']):

    def __init__(self, rpc: Rpc, id: int) -> None:
        self.rpc = rpc
        self.id = id


class RpcArgs(Dat['RpcArgs']):

    @staticmethod
    def cons(args: List[Any]=Nil, bang: bool=False) -> 'RpcArgs':
        return RpcArgs(args, bang)

    def __init__(self, args: List[Any], bang: bool) -> None:
        self.args = args
        self.bang = bang

    @property
    def string(self) -> str:
        return self.args.join_comma


__all__ = ('Rpc', 'ActiveRpc', 'RpcArgs',)
