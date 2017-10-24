from typing import Optional
from ribosome import NvimStatePlugin, msg_command

from amino import List, Right, Left, Either, Id, IO
from amino.state import IdState, StateT, EitherState
from ribosome.logging import Logging
from ribosome.machine.message_base import pmessage
from ribosome.machine.state import UnloopedRootMachine, SubTransitions, Component, ComponentMachine
from ribosome.nvim import NvimFacade, HasNvim, AsyncVimProxy
from ribosome.data import Data
from ribosome.record import field
from ribosome.machine import trans
from ribosome.machine.machine import Machine

Msg = pmessage('Msg')
Msg2 = pmessage('Msg2')
Msg3 = pmessage('Msg3')
Msg4 = pmessage('Msg4')
Msg5 = pmessage('Msg5')


class SpecEnv(Data):
    vim = field(AsyncVimProxy)


class HTrans(Component, Logging):

    @trans.one(Msg, trans.e, trans.st, trans.io)
    def msg(self) -> Either[str, StateT[Id, SpecEnv, IO[Msg2]]]:
        return Right(IdState.pure(IO.pure(Msg2())))

    @trans.one(Msg2, trans.e)
    def msg2(self) -> Either[str, Msg]:
        return Left('nothing')

    @trans.unit(Msg3, trans.st)
    def unit(self) -> IdState[SpecEnv, Msg]:
        self.log.info('unit')
        return IdState.set(1)

    @trans.one(Msg4, trans.st)
    def st(self) -> EitherState[SpecEnv, Msg]:
        return EitherState.pure(Msg5())

    @trans.one(Msg5, trans.st)
    def est_fail(self) -> EitherState[SpecEnv, Msg]:
        return EitherState(Left('est'))


class Component(ComponentMachine):

    def __init__(self, vim: NvimFacade, parent: Optional[Machine]=None) -> None:
        super().__init__(vim, HTrans, 'handler', parent)


class Mach(UnloopedRootMachine):
    _data_type = SpecEnv

    def __init__(self, vim: NvimFacade, **kw) -> None:
        plug = 'integration._support.handler'
        UnloopedRootMachine.__init__(self, vim, List(plug), **kw)

    @property
    def init(self):
        return SpecEnv(vim=self.vim)


class HandlerSpecPlugin(NvimStatePlugin, Logging, pname='handler', prefix='han'):

    def __init__(self, *a, **kw) -> None:
        super().__init__(*a, **kw)
        self._state = None

    def state(self) -> Mach:
        if self._state is None:
            self._state = Mach(self.vim.proxy, name='handler')
        return self._state

    def stage_1(self) -> None:
        self.state().start()

    @msg_command(Msg, sync=True)
    def msg(self):
        pass

    @msg_command(Msg3, sync=True)
    def unit(self):
        pass

    @msg_command(Msg4, sync=True)
    def est(self):
        pass

__all__ = ('HandlerSpecPlugin',)
