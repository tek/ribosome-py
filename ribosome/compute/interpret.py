from typing import TypeVar, Callable, Any
from concurrent.futures import wait, ThreadPoolExecutor

from amino.case import Case
from amino import IO, List, Either, Lists, __
from amino.io import IOException

from ribosome.compute.output import (ProgOutputInterpreter, ProgIOInterpreter, ProgOutputIO, ProgScalarIO,
                                     ProgGatherIOs, ProgScalarSubprocess, ProgGatherSubprocesses, GatherIOs,
                                     GatherSubprocesses, ProgIOCustom, ProgOutputUnit, ProgOutputResult)
from ribosome.compute.prog import Prog
from ribosome.compute.program import ProgramInterpreter
from ribosome import ribo_log
from ribosome.process import Subprocess

A = TypeVar('A')
B = TypeVar('B')


def gather_ios(gio: GatherIOs[A]) -> List[Either[IOException, A]]:
    with ThreadPoolExecutor(thread_name_prefix='ribosome_dio') as executor:
        ribo_log.debug(f'executing ios {gio.ios}')
        futures = gio.ios.map(lambda i: executor.submit(i.attempt_run))
        completed, timed_out = wait(futures, timeout=gio.timeout)
        ribo_log.debug(f'completed ios {completed}')
        if timed_out:
            ribo_log.debug(f'ios timed out: {timed_out}')
        return Lists.wrap(completed).map(__.result(timeout=gio.timeout))


def gather_subprocesses(gio: GatherSubprocesses[A]) -> List[Either[IOException, A]]:
    ribo_log.debug(f'gathering {gio}')
    popens = gio.subprocs.map(__.execute())
    return gather_ios(GatherIOs(popens, gio.timeout))


class interpret_io(Case[ProgIOInterpreter, Prog[A]], alg=ProgIOInterpreter):

    def __init__(self, custom: Callable[[Any], Prog[A]]) -> None:
        self.custom = custom

    def prog_scalar_io(self, po: ProgScalarIO, output: IO[A]) -> Prog[A]:
        return Prog.from_either(output.attempt)

    def prog_gather_ios(self, po: ProgGatherIOs, output: GatherIOs[A]) -> Prog[A]:
        return Prog.pure(gather_ios(output))

    def prog_scalar_subprocess(self, po: ProgScalarSubprocess, output: Subprocess[A]) -> Prog[A]:
        return Prog.from_either(output.execute().attempt)

    def prog_gather_subprocesses(self, po: ProgGatherSubprocesses, output: GatherSubprocesses[A]) -> Prog[A]:
        return Prog.pure(gather_subprocesses(output))

    def prog_io_custom(self, po: ProgIOCustom, output: Any) -> Prog[A]:
        return self.custom(output)


class interpret(Case[ProgOutputInterpreter, Prog[B]], alg=ProgOutputInterpreter):

    def __init__(self, custom: Callable[[A], Prog[B]]) -> None:
        self.custom = custom

    def prog_output_io(self, po: ProgOutputIO, output: IO[B]) -> Prog[B]:
        return interpret_io(self.custom)(po.interpreter, output)

    def prog_output_unit(self, po: ProgOutputUnit, output: Any) -> Prog[None]:
        return Prog.pure(None)

    def prog_output_result(self, po: ProgOutputResult, output: B) -> Prog[B]:
        return Prog.pure(output)


def default_interpreter(custom: Callable[[A], Prog[B]]) -> ProgramInterpreter:
    return ProgramInterpreter(lambda a: lambda r: interpret(custom)(a, r))


plain_default_interpreter = default_interpreter(lambda a: Prog.error(f'no custom interpreter ({a})'))


__all__ = ('default_interpreter',)
