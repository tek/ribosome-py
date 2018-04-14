from typing import TypeVar, Any, Generic, cast

from amino import List, _
from amino.do import do, Do
from amino.case import Case

from ribosome.nvim.io.state import NS
from ribosome.compute.prog import Prog, ProgBind, ProgPure, ProgError, ProgExec, ProgInterpret
from ribosome.compute.output import ProgOutputInterpreter, ProgOutputResult, ProgOutputUnit
from ribosome.compute.wrap_data import ProgWrappers
from ribosome.config.settings import Settings
from ribosome.data.plugin_state import PluginState
from ribosome.compute.program import bind_program, Program

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


class eval_prog(Generic[A, B, R, D, S, CC], Case[Prog[A], NS[PluginState[S, D, CC], A]], alg=Prog):

    @do(NS[PluginState[S, D, CC], A])
    def prog_exec(self, prog: ProgExec[B, A, R, Any]) -> Do:
        yield transform_prog_state(prog.code, prog.wrappers)

    @do(NS[PluginState[S, D, CC], A])
    def prog_bind(self, prog: ProgBind[Any, A]) -> Do:
        result = yield self(prog.fa)
        next_trans = prog.f(result)
        yield self(next_trans)

    @do(NS[PluginState[S, D, CC], A])
    def prog_interpret(self, prog: ProgInterpret[Any, A]) -> Do:
        output = yield self(prog.prog)
        yield self(prog.interpret(output))

    @do(NS[PluginState[S, D, CC], A])
    def prog_pure(self, prog: ProgPure[A]) -> Do:
        yield NS.pure(prog.value)

    @do(NS[PluginState[S, D, CC], A])
    def prog_error(self, prog: ProgError[A]) -> Do:
        yield NS.error(prog.msg)


@do(NS[PluginState[S, D, CC], A])
def run_prog(program: Program[A], args: List[Any]) -> Do:
    interpreter = yield NS.inspect(_.program_interpreter)
    yield eval_prog.match(bind_program(program, interpreter, args))


__all__ = ('run_prog',)
