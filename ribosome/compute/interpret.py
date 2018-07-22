from typing import TypeVar, Callable, Any
from concurrent.futures import wait, ThreadPoolExecutor

from amino.case import Case
from amino import IO, List, Either, Lists, __, Maybe, Nothing, do, Do
from amino.io import IOException

from ribosome import ribo_log
from ribosome.compute.output import (ProgOutput, ProgIO, ProgOutputIO, ProgScalarIO, ProgGatherIOs,
                                     ProgScalarSubprocess, ProgGatherSubprocesses, GatherIOs, GatherSubprocesses,
                                     ProgIOCustom, ProgOutputUnit, ProgOutputResult, ProgIOEcho, Echo, GatherItem,
                                     GatherIO, GatherSubprocess, GatherResult, GatherIOResult, GatherSubprocessResult,
                                     Gather, ProgGather)
from ribosome.compute.prog import Prog
from ribosome.compute.program import Program
from ribosome.process import Subprocess
from ribosome.nvim.io.state import NS

A = TypeVar('A')
B = TypeVar('B')
D = TypeVar('D')


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


class gather_item(Case[GatherItem[A], IO[GatherResult[A]]], alg=GatherItem):

    def io(self, a: GatherIO[A]) -> IO[GatherResult[A]]:
        return a.io.map(GatherIOResult)

    def subproc(self, a: GatherSubprocess[A]) -> IO[GatherResult[A]]:
        return a.subprocess.execute().map(GatherSubprocessResult)


def gather_mixed(gio: Gather[A]) -> List[Either[IOException, GatherSubprocessResult[A]]]:
    ios = gio.items.map(gather_item.match)
    return gather_ios(GatherIOs(ios, gio.timeout))


ProgIOInterpreter = Callable[[ProgIO, Any], Prog[A]]


def default_logger(echo: Echo) -> NS[D, None]:
    io = echo.messages.traverse(lambda m: IO.delay(ribo_log.log, echo.level, m), IO)
    return NS.from_io(io).replace(None)


default_logger_program = Program.lift(default_logger)


class interpret_io(Case[ProgIO, Prog[A]], alg=ProgIO):

    def __init__(self, custom: Callable[[Any], Prog[A]], logger: Maybe[Program]=Nothing) -> None:
        self.custom = custom
        self.logger = logger

    def prog_scalar_io(self, po: ProgScalarIO, output: IO[A]) -> Prog[A]:
        return Prog.from_either(output.attempt)

    def prog_gather_ios(self, po: ProgGatherIOs, output: GatherIOs[A]) -> Prog[Prog[List[Either[IOException, A]]]]:
        return Prog.pure(gather_ios(output))

    def prog_scalar_subprocess(self, po: ProgScalarSubprocess, output: Subprocess[A]) -> Prog[A]:
        return Prog.from_either(output.execute().attempt)

    def prog_gather_subprocesses(self, po: ProgGatherSubprocesses, output: GatherSubprocesses[A]
                                 ) -> Prog[List[Either[IOException, A]]]:
        return Prog.pure(gather_subprocesses(output))

    @do(Prog[None])
    def prog_io_echo(self, po: ProgIOEcho, output: Echo) -> Do:
        logger = self.logger | (lambda: default_logger_program)
        yield logger(output).replace(None)

    def prog_io_custom(self, po: ProgIOCustom, output: Any) -> Prog[A]:
        return self.custom(output)

    def prog_gather(self, po: ProgGather, output: Gather[A]) -> Prog[List[Either[IOException, A]]]:
        return Prog.pure(gather_mixed(output))


class interpret(Case[ProgOutput, Prog[B]], alg=ProgOutput):

    def __init__(self, io: ProgIOInterpreter[B]) -> None:
        self.io = io

    def prog_output_io(self, po: ProgOutputIO, output: IO[B]) -> Prog[B]:
        return self.io(po.io, output)

    def prog_output_unit(self, po: ProgOutputUnit, output: Any) -> Prog[None]:
        return Prog.pure(None)

    def prog_output_result(self, po: ProgOutputResult, output: B) -> Prog[B]:
        return Prog.pure(output)


def no_interpreter(po: ProgOutputIO, a: Any) -> Prog[A]:
    return Prog.error(f'no custom interpreter ({a})')


__all__ = ('ProgIOInterpreter', 'interpret_io', 'interpret', 'no_interpreter')
