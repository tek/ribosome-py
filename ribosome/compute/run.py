from typing import TypeVar, Any, Generic

from amino import List, _, __
from amino.do import do, Do
from amino.case import Case

from ribosome.nvim.io.state import NS
from ribosome.compute.prog import Prog, ProgBind, ProgPure, ProgError, ProgExec
from ribosome.compute.wrap_data import ProgWrappers
from ribosome.data.plugin_state import PluginState
from ribosome.compute.program import bind_program, Program
from ribosome.compute.interpret import interpret

A = TypeVar('A')
B = TypeVar('B')
D = TypeVar('D')
R = TypeVar('R')
CC = TypeVar('CC')


@do(NS[PluginState[D, CC], A])
def transform_prog_state(st: NS[R, A], wrappers: ProgWrappers[PluginState[D, CC], R]) -> Do:
    yield st.transform_s(wrappers.get, wrappers.put)


def log_prog(prog: ProgExec) -> NS[PluginState[D, CC], None]:
    return NS.pure(None) if prog.name in ('program_log', 'pure', 'lift') else NS.modify(__.log_prog(prog.name))


class eval_prog(Generic[A, B, R, D, CC], Case[Prog[A], NS[PluginState[D, CC], A]], alg=Prog):

    @do(NS[PluginState[D, CC], A])
    def prog_exec(self, prog: ProgExec[B, A, R, Any]) -> Do:
        yield log_prog(prog)
        io_interpreter = yield NS.inspect(_.io_interpreter)
        output = yield transform_prog_state(prog.code, prog.wrappers)
        yield self(interpret(io_interpreter)(prog.output_type, output))

    @do(NS[PluginState[D, CC], A])
    def prog_bind(self, prog: ProgBind[Any, A]) -> Do:
        result = yield self(prog.fa)
        yield self(prog.f(result))

    @do(NS[PluginState[D, CC], A])
    def prog_pure(self, prog: ProgPure[A]) -> Do:
        yield NS.pure(prog.value)

    @do(NS[PluginState[D, CC], A])
    def prog_error(self, prog: ProgError[A]) -> Do:
        yield NS.error(prog.msg)


@do(NS[PluginState[D, CC], A])
def run_prog(program: Program[A], args: List[Any]) -> Do:
    yield eval_prog.match(bind_program(program, args))


__all__ = ('run_prog',)
