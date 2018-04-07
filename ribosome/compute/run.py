from typing import TypeVar, Any, Generic, cast

from amino import List
from amino.do import do, Do
from amino.lenses.lens import lens
from amino.case import Case

from ribosome.nvim.io.state import NS
from ribosome.compute.prog import Prog, ProgBind, ProgPure, ProgError, ProgMap, Program, ProgExec, bind_program
from ribosome.compute.data import CompilationSuccess
from ribosome.compute.output import ProgOutputInterpreter, ProgOutputResult, ProgOutputUnit
from ribosome.compute.wrap_data import ProgWrappers


from ribosome.request.args import ArgValidator
from ribosome.compute.data import Compilation, CompilationFailure
from ribosome.config.settings import Settings
from ribosome.plugin_state import PluginState

A = TypeVar('A')
B = TypeVar('B')
D = TypeVar('D')
S = TypeVar('S', bound=Settings)
CC = TypeVar('CC')


def compile_program(prog: Program[B, A]) -> Compilation[D, A]:
    val = ArgValidator(prog.params_spec)
    return val.either(prog.args, 'prog', prog.name).cata(
        CompilationFailure,
        lambda a: CompilationSuccess(prog.fun(*prog.args))
    )


@do(NS[PluginState[S, D, CC], Any])
def transform_prog_state(st: NS[D, A], wrappers: ProgWrappers[A, B, D]) -> Do:
    yield st.zoom(lens.data).transform_s(wrappers.get, wrappers.put)


class interpret(Generic[A, B], Case[ProgOutputInterpreter[A, B], Prog[B]], alg=ProgOutputInterpreter):

    def __init__(self, output: A) -> None:
        self.output = output

    def prog_output_result(self, i: ProgOutputResult[B]) -> Prog[B]:
        return ProgPure(cast(B, self.output))

    def prog_output_unit(self, i: ProgOutputUnit) -> Prog[B]:
        return ProgPure(cast(B, None))

    def case_default(self, i: Any) -> Prog[B]:
        return Prog.error(f'`interpret` not implemented for {i}')


# FIXME recursive
class eval_prog(Case[Prog, A], alg=Prog):

    @do(NS[PluginState[S, D, CC], A])
    def prog_exec(self, program: ProgExec[Any, A]) -> Do:
        output = yield transform_prog_state(program.code, program.wrappers)
        yield self(interpret(output)(program.interpreter))

    @do(NS[PluginState[S, D, CC], A])
    def prog_bind(self, prog: ProgBind[Any, A]) -> Do:
        result = yield self(prog.fa)
        next_trans = prog.f(result)
        yield self(next_trans)

    @do(NS[PluginState[S, D, CC], A])
    def prog_map(self, prog: ProgMap[Any, A]) -> Do:
        yield NS.pure(prog.value)

    @do(NS[PluginState[S, D, CC], A])
    def prog_pure(self, prog: ProgPure[A]) -> Do:
        yield NS.pure(prog.value)

    @do(NS[PluginState[S, D, CC], A])
    def prog_error(self, prog: ProgError[A]) -> Do:
        yield NS.error(prog.msg)


@do(NS)
def run_prog(program: Prog[A], args: List[Any]) -> Do:
    yield eval_prog.match(bind_program(program, args))


__all__ = ('compile_program',)
