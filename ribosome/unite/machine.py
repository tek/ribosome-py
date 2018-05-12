import abc

from amino import List, __, _

from ribosome.unite import UniteMessage, UniteSource
from ribosome.unite.data import UniteKind, UniteSyntax
from ribosome.compute.api import prog
from ribosome.config.component import Component


class Unite(Component):

    @prog.msg.one(UniteSyntax, prog.m, prog.io)
    def syntax(self):
        return self.machine.syntax(self.msg.source)


class UniteMachine:

    def __init__(self) -> None:
        self._unite_ready = False

    def prepare(self, msg):
        if not self._unite_ready and isinstance(msg, UniteMessage):
            self._setup_unite()

    def _setup_unite(self):
        self.sources % __.define(self.vim)
        self.kinds % __.define(self.vim)
        self._unite_ready = True

    @abc.abstractproperty
    def sources(self) -> List[UniteSource]:
        ...

    @abc.abstractproperty
    def kinds(self) -> List[UniteKind]:
        ...

    def syntax(self, source):
        return self.sources.find(_.name == source) / __.syntax_task(self.vim.buffer.syntax)


__all__ = ('Unite',)
