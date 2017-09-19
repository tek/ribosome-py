from ribosome import NvimStatePlugin

from amino.lazy import lazy
from amino import List, Right, Left, Either, Id, IO
from amino.state import IdState, StateT, EitherState
from ribosome.logging import Logging
from ribosome.request import msg_command
from ribosome.machine.message_base import message
from ribosome.machine.state import UnloopedRootMachine, SubMachine, SubTransitions
from ribosome.nvim import NvimFacade, HasNvim, AsyncVimProxy
from ribosome.data import Data
from ribosome.record import field
from ribosome.machine.base import MachineBase
from ribosome.machine import trans

Msg = message('Msg')
Msg2 = message('Msg2')
Msg3 = message('Msg3')
Msg4 = message('Msg4')
Msg5 = message('Msg5')


class Env(Data):
    vim = field(AsyncVimProxy)


class HTrans(SubTransitions, HasNvim, Logging):

    def __init__(self, machine, *a, **kw) -> None:
        SubTransitions.__init__(self, machine, *a, **kw)
        HasNvim.__init__(self, machine.vim)

    @trans.one(Msg, trans.e, trans.st, trans.io)
    def msg(self) -> Either[str, StateT[Id, Env, IO[Msg2]]]:
        return Right(IdState.pure(IO.pure(Msg2())))

    @trans.one(Msg2, trans.e)
    def msg2(self) -> Either[str, Msg]:
        return Left('nothing')

    @trans.unit(Msg3, trans.st)
    def unit(self) -> IdState[Env, Msg]:
        self.log.info('unit')
        return IdState.set(1)

    @trans.one(Msg4, trans.est)
    def est(self) -> EitherState[Env, Msg]:
        return EitherState.pure(Msg5())

    @trans.one(Msg5, trans.est)
    def est_fail(self) -> EitherState[Env, Msg]:
        return EitherState(Left('est'))


class Plugin(SubMachine, HasNvim, Logging):
    Transitions = HTrans

    def __init__(self, vim: NvimFacade, parent=None, title=None) -> None:
        MachineBase.__init__(self, parent, title=title)
        HasNvim.__init__(self, vim)


class Mach(UnloopedRootMachine):
    _data_type = Env

    def __init__(self, vim: NvimFacade, **kw) -> None:
        plug = 'integration._support.handler'
        UnloopedRootMachine.__init__(self, vim, List(plug), **kw)

    @property
    def title(self):
        return 'mach'

    @property
    def init(self):
        return Env(vim=self.vim)


class HandlerSpecPlugin(NvimStatePlugin, Logging, pname='handler'):

    @lazy
    def _state(self) -> Mach:
        return Mach(self.vim.proxy, title='handler')

    def state(self) -> Mach:
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
