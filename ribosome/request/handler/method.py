import abc
from typing import Type, TypeVar

from amino.dat import ADT

from ribosome.request.rpc import RpcHandlerSpec, RpcCommandSpec, RpcFunctionSpec, RpcAutocommandSpec

RHS = TypeVar('RHS', bound=RpcHandlerSpec)


class RpcMethod(ADT['RpcMethod'], base=True):

    @abc.abstractproperty
    def spec_type(self) -> Type[RHS]:
        ...

    @abc.abstractproperty
    def method(self) -> str:
        ...


class CmdMethod(RpcMethod):

    @property
    def spec_type(self) -> Type[RHS]:
        return RpcCommandSpec

    @property
    def method(self) -> str:
        return 'command'


class FunctionMethod(RpcMethod):

    @property
    def spec_type(self) -> Type[RHS]:
        return RpcFunctionSpec

    @property
    def method(self) -> str:
        return 'function'


class AutocmdMethod(RpcMethod):

    @property
    def spec_type(self) -> Type[RHS]:
        return RpcAutocommandSpec

    @property
    def method(self) -> str:
        return 'autocmd'


__all__ = ('RpcMethod', 'CmdMethod', 'FunctionMethod', 'AutocmdMethod')
