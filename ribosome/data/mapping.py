import abc
from uuid import uuid4, UUID
from typing import Tuple

from amino import Dat, Map, Boolean, ADT, List, Maybe, Lists
from amino.boolean import false

from ribosome.compute.program import Program


class MapMode(ADT['MapMode']):

    @abc.abstractproperty
    def mnemonic(self) -> str:
        ...


class mapmode:

    class Normal(MapMode):

        @property
        def mnemonic(self) -> str:
            return 'n'

    class Operator(MapMode):

        @property
        def mnemonic(self) -> str:
            return 'o'

    class Visual(MapMode):

        @property
        def mnemonic(self) -> str:
            return 'x'

    class Select(MapMode):

        @property
        def mnemonic(self) -> str:
            return 's'

    class VisualSelect(MapMode):

        @property
        def mnemonic(self) -> str:
            return 'v'

    class Insert(MapMode):

        @property
        def mnemonic(self) -> str:
            return 'i'

    class CommandLine(MapMode):

        @property
        def mnemonic(self) -> str:
            return 'c'

    class Terminal(MapMode):

        @property
        def mnemonic(self) -> str:
            return 't'

    class Language(MapMode):

        @property
        def mnemonic(self) -> str:
            return 'l'


class Mapping(Dat['Mapping']):

    @staticmethod
    def cons(keys: str, buffer: Boolean=false, modes: List[MapMode]=None, uuid: UUID=None) -> 'Mapping':
        modes1 = List(mapmode.Normal()) if modes is None else modes
        return Mapping(keys, Boolean(buffer), modes1, uuid or uuid4())

    def __init__(self, keys: str, buffer: Boolean, modes: List[MapMode], uuid: UUID) -> None:
        self.keys = keys
        self.buffer = buffer
        self.modes = modes
        self.uuid = uuid


class Mappings(Dat['Mappings']):

    @staticmethod
    def cons(*mappings: List[Tuple[Mapping, Program]]) -> 'Mappings':
        return Mappings(Map(Lists.wrap(mappings).map2(lambda m, p: (str(m.uuid), (m, p)))))

    def __init__(self, mappings: Map[str, Tuple[Mapping, Program]]) -> None:
        self.mappings = mappings

    def lift(self, mapping: Mapping) -> Maybe[Program]:
        return self.mappings.lift(str(mapping.uuid))


__all__ = ('Mapping', 'Mappings')
