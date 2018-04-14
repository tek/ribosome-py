from typing import TypeVar

from kallikrein import Expectation, k
from kallikrein.matchers import contain, equal
from kallikrein.matchers.tuple import tupled
from kallikrein.matchers.either import be_right
from kallikrein.matchers.match_with import match_with
from kallikrein.expectable import Expectable

from amino.test.spec import SpecBase
from amino import List, Map, do, Do, Dat, _, Nil, __, IO, Right
from amino.state import State
from amino.lenses.lens import lens

from ribosome.config.config import Config
from ribosome.config.component import Component, ComponentData
from ribosome.test.integration.run import RequestHelper
from ribosome.nvim.io.data import NError
from ribosome.nvim.io.state import NS
from ribosome.config.settings import Settings
from ribosome.compute.api import prog
from ribosome.request.handler.handler import RequestHandler
from ribosome.compute.run import run_prog
from ribosome.test.klk import kn
from ribosome.compute.prog import Prog
from ribosome.config.resources import Resources
from ribosome.compute.ribosome import Ribosome
from ribosome.compute.ribosome_api import Ribo
from ribosome.compute.program import Program
from ribosome.compute.interpret import GatherIOs, GatherSubprocesses
from ribosome.process import Subprocess, SubprocessResult
from ribosome.compute.output import Echo

A = TypeVar('A')


class Compon(Dat['Compon']):
    pass


class CoreData(Dat['CoreData']):

    @staticmethod
    def cons(x: int=-15) -> 'CoreData':
        return CoreData(x)

    def __init__(self, x: int) -> None:
        self.x = x


class ExtraData(Dat['ExtraData']):

    @staticmethod
    def cons(y: int=-19) -> 'ExtraData':
        return ExtraData(y)

    def __init__(self, y: int) -> None:
        self.y = y


class CompoComponent(Dat['CompoComponent']):

    def __init__(self, baseline: int) -> None:
        self.baseline = baseline


@prog.result
@do(State[ComponentData[CoreData, ExtraData], int])
def t1(a: int) -> Do:
    yield State.modify(lens.comp.y.modify(_ + 5))
    return a + 2


@prog.result
@do(State[ComponentData[CoreData, ExtraData], int])
def t2_b(a: int) -> Do:
    yield State.inspect(_.comp.y + a + 39)


@prog.do
@do(Prog)
def t2(a: int) -> Do:
    yield t2_b(a)


@prog.result
@do(State[CoreData, int])
def t3(a: int) -> Do:
    yield State.modify(lens.x.modify(_ + a))
    return a


@prog.do
@do(Prog)
def tm() -> Do:
    a = yield t1(0)
    b = yield t2(a)
    yield t3(b)


c1: Component = Component.cons(
    'c1',
    request_handlers=List(
        RequestHandler.trans_function(t1)(),
    ),
    config=CompoComponent(13),
    state_ctor=ExtraData.cons,
    state_type=ExtraData,
)

c2: Component = Component.cons(
    'c2',
    request_handlers=List(
        RequestHandler.trans_function(t2)(),
        RequestHandler.trans_function(t2_b)(),
    ),
    state_ctor=ExtraData.cons,
    state_type=ExtraData,
)


config: Config = Config.cons(
    'compo',
    components=Map(c1=c1, c2=c2),
    core_components=List('c1', 'c2'),
    state_ctor=CoreData.cons,
    request_handlers=List(
        RequestHandler.trans_function(tm)(),
        RequestHandler.trans_function(t3)(),
    ),
)
helper = RequestHelper.strict(config)


@prog.do
@do(Prog[None])
def n3(a: int) -> Do:
    yield Prog.error('stop')


@prog.do
@do(Prog[None])
def n2() -> Do:
    yield Prog.pure(7)


@prog.do
@do(Prog[None])
def n1() -> Do:
    a = yield n2()
    b = yield n3(a)
    return b + 7


@prog.result
@do(NS[Resources[Settings, ComponentData[CoreData, ExtraData], Compon], str])
def comp_res() -> Do:
    s = yield NS.inspect(_.components)
    comp = yield NS.from_either(s.by_type(ExtraData))
    yield NS.modify(lens.data.comp.y.set(29))
    return comp.name


@prog.result
@do(NS[CoreData, None])
def root() -> Do:
    yield NS.pure(13)


def run_a(t: Program) -> Expectable:
    return kn(helper.vim, lambda: run_prog(t, Nil).run_a(helper.state))


def run(t: Program) -> Expectable:
    return kn(helper.vim, lambda: run_prog(t, Nil).run(helper.state))


@prog.result
@do(NS[Ribosome[Settings, CoreData, Compon, ExtraData], int])
def mod_main() -> Do:
    yield Ribo.modify_main(__.set.x(437))
    yield Ribo.main()


@prog.result
@do(NS[Ribosome[Settings, CoreData, Compon, ExtraData], int])
def mod_comp() -> Do:
    yield Ribo.modify_comp(__.set.y(954))
    yield Ribo.comp()


@prog.io
@do(NS[CoreData, IO[int]])
def scalar_io() -> Do:
    yield NS.pure(IO.pure(1046))


@prog.io.gather
@do(NS[CoreData, IO[int]])
def gather_ios() -> Do:
    yield NS.pure(GatherIOs(List(IO.pure(5), IO.pure(8)), 1.0))


@prog.subproc
@do(NS[CoreData, Subprocess[str]])
def scalar_subproc() -> Do:
    yield NS.pure(Subprocess('echo', List('692'), None, 1.0))


@prog.subproc.gather
@do(NS[CoreData, GatherSubprocesses[str]])
def gather_subprocs() -> Do:
    yield NS.pure(GatherSubprocesses(List(
        Subprocess('echo', List('84'), None, 1.0), Subprocess('echo', List('39'), None, 1.0)
    ), 1.0))


@prog.echo
@do(NS[CoreData, Echo])
def log_message() -> Do:
    yield NS.pure(Echo(List('hello'), Echo.info))


class ProgSpec(SpecBase):
    '''
    nest several trans $nest
    fail on error $error
    component with resources $comp_res
    root without extras $root

    Ribosome state
    modify main data $mod_main
    modify component $mod_comp

    IO output
    scalar IO $scalar_io
    gather IOs nondeterministically $gather_ios
    scalar subprocess $scalar_subproc
    gather subprocesses $gather_subprocs
    log a message $log_message
    '''

    def nest(self) -> Expectation:
        return run_a(tm).must(contain(27))

    def error(self) -> Expectation:
        return run_a(n1) == NError('stop')

    def comp_res(self) -> Expectation:
        def state_updated(a) -> Expectation:
            return k(a.data_by_name(c1.name) / _.y).must(be_right(29))
        return run(comp_res).must((contain(tupled(2)((match_with(state_updated), equal(c1.name))))))

    def root(self) -> Expectation:
        return run_a(root).must(contain(13))

    def mod_main(self) -> Expectation:
        return run_a(mod_main).must(contain(CoreData.cons(437)))

    def mod_comp(self) -> Expectation:
        return run_a(mod_comp).must(contain(ExtraData.cons(954)))

    def scalar_io(self) -> Expectation:
        return run_a(scalar_io).must(contain(1046))

    def gather_ios(self) -> Expectation:
        return run_a(gather_ios).must(contain(contain(Right(5)) & contain(Right(8))))

    def scalar_subproc(self) -> Expectation:
        return run_a(scalar_subproc).must(contain(SubprocessResult(0, List('692'), Nil, None)))

    def gather_subprocs(self) -> Expectation:
        return run_a(gather_subprocs).must(contain(
            contain(Right(SubprocessResult(0, List('84'), Nil, None))) &
            contain(Right(SubprocessResult(0, List('39'), Nil, None)))
        ))

    def log_message(self) -> Expectation:
        return run_a(log_message).must(contain(None))


__all__ = ('ProgSpec',)
