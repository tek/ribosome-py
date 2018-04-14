from typing import TypeVar, Any, Generic, cast

from amino import List
from amino.do import do, Do
from amino.case import Case

from ribosome.nvim.io.state import NS
from ribosome.compute.prog import Prog, ProgBind, ProgPure, ProgError, ProgExec, bind_program, Program
from ribosome.compute.output import ProgOutputInterpreter, ProgOutputResult, ProgOutputUnit
from ribosome.compute.wrap_data import ProgWrappers
from ribosome.config.settings import Settings
from ribosome.data.plugin_state import PluginState

A = TypeVar('A')
B = TypeVar('B')
D = TypeVar('D')
R = TypeVar('R')
S = TypeVar('S', bound=Settings)
CC = TypeVar('CC')


@do(NS[PluginState[S, D, CC], A])
def transform_prog_state(st: NS[R, A], wrappers: ProgWrappers[PluginState[D, S, CC], R]) -> Do:
    yield st.transform_s(wrappers.get, wrappers.put)


class interpret(Generic[A, B], Case[ProgOutputInterpreter[A, B], Prog[B]], alg=ProgOutputInterpreter):

    def prog_output_result(self, i: ProgOutputResult[B], output: B) -> Prog[B]:
        return ProgPure(output)

    def prog_output_unit(self, i: ProgOutputUnit, output: A) -> Prog[B]:
        return ProgPure(cast(B, None))

    def case_default(self, i: ProgOutputInterpreter[A, B], output: A) -> Prog[B]:
        return Prog.error(f'`interpret` not implemented for {i}')


class eval_prog(Case[Prog[A], NS[PluginState[S, D, CC], A]], alg=Prog):

    @do(NS[PluginState[S, D, CC], A])
    def prog_exec(self, prog: ProgExec[B, A, PluginState[S, D, CC], Any]) -> Do:
        output = yield transform_prog_state(prog.code, prog.wrappers)
        yield self(interpret.match(prog.interpreter, output))

    @do(NS[PluginState[S, D, CC], A])
    def prog_bind(self, prog: ProgBind[Any, A]) -> Do:
        result = yield self(prog.fa)
        next_trans = prog.f(result)
        yield self(next_trans)

    @do(NS[PluginState[S, D, CC], A])
    def prog_pure(self, prog: ProgPure[A]) -> Do:
        yield NS.pure(prog.value)

    @do(NS[PluginState[S, D, CC], A])
    def prog_error(self, prog: ProgError[A]) -> Do:
        yield NS.error(prog.msg)


@do(NS[PluginState[S, D, CC], A])
def run_prog(program: Program[A], args: List[Any]) -> Do:
    yield eval_prog.match(bind_program(program, args))


__all__ = ('run_prog',)
