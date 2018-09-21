from typing import Callable, TypeVar
from threading import Event
from queue import Queue

from amino import do, Do, IO

from ribosome.nvim.io.compute import NvimIO, lift_n_result
from ribosome.nvim.io.api import N
from ribosome.nvim.io.data import NResult, NError
from ribosome.util.menu.prompt.data import PromptInterrupt, InputResources
from ribosome.nvim.io.state import NS

A = TypeVar('A')
B = TypeVar('B')


@do(IO[None])
def stop_prompt(queue: Queue, stop: Event) -> Do:
    yield IO.delay(stop.set)
    yield IO.delay(queue.put, PromptInterrupt())


@do(NS[InputResources[A, B], None])
def stop_prompt_s() -> Do:
    res = yield NS.get()
    yield NS.lift(N.from_io(stop_prompt(res.inputs, res.stop)))


def intercept_interrupt_result(queue: Queue, stop: Event, default: A) -> Callable[[NResult[A]], NvimIO[A]]:
    @do(NvimIO[A])
    def intercept_interrupt_result(result: NResult[A]) -> Do:
        yield N.from_io(stop_prompt(queue, stop))
        yield (
            N.pure(default)
            if isinstance(result, NError) and 'Keyboard interrupt' in str(result.error) else
            lift_n_result.match(result)
        )
    return intercept_interrupt_result


def intercept_interrupt(queue: Queue, stop: Event, default: A, thunk: NvimIO[A]) -> NvimIO[A]:
    return N.recover_failure(thunk, intercept_interrupt_result(queue, stop, default))


__all__ = ('stop_prompt', 'intercept_interrupt', 'stop_prompt_s',)
