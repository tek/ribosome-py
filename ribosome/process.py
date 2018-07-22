import abc
from pathlib import Path
import shutil
from contextlib import contextmanager
from typing import Tuple, Awaitable, Any, Generic, TypeVar
from subprocess import PIPE, Popen

import asyncio
from asyncio.subprocess import PIPE as APIPE

from amino import Map, Future, __, Boolean, _, L, List, Maybe, IO, Lists, do, Either
from amino.lazy import lazy
from amino.either import Right, Left
from amino.util.string import ToStr
from amino.dat import Dat
from amino.do import Do
from amino.logging import module_log

import ribosome
from ribosome.logging import Logging
from ribosome.nvim.api.data import NvimApi

log = module_log()


class Result(ToStr):

    def __init__(self, job: 'Job', success: bool, out: str, err: str) -> None:
        self.job = job
        self.success = Boolean(success)
        self.out = out
        self.err = err

    def _arg_desc(self) -> List[str]:
        return List(str(self.job), str(self.success), self.msg)

    @property
    def msg(self):
        return self.err if self.err else self.out

    def either(self, good, bad):
        return self.success.maybe(Right(good)) | Left(bad)


class JobClient(Dat['JobClient']):

    def __init__(self, cwd: Path, name: str) -> None:
        self.cwd = cwd
        self.name = name


class Job(Dat['Job']):

    def __init__(self, client: JobClient, exe: str, args: List, kw: Map, loop: Any, pipe_in: Maybe[str]) -> None:
        self.client = client
        self.exe = exe
        self.args = args
        self.kw = kw
        self.loop = loop
        self.pipe_in = pipe_in

    @lazy
    def status(self):
        return Future(loop=self.loop)

    @lazy
    def stdin(self):
        return self.pipe_in.map(__.encode()) | None

    def finish(self, f: Future) -> None:
        code, out, err = f.result()
        self.finish_strict(code, out, err)

    def finish_strict(self, code: int, out: str, err: str) -> None:
        self.status.set_result(self.result_strict(code, out, err))

    def result_strict(self, code: int, out: str, err: str) -> None:
        return Result(self, code == 0, out, err)

    def finish_success(self, out: str) -> None:
        self.finish_strict(0, out, '')

    def cancel(self, reason: str):
        self.status.set_result(Result(self, False, '', 'canceled: {}'.format(reason)))

    @property
    def valid(self):
        return (
            not self.status.done() and
            self.cwd.is_dir() and (
                Path(self.exe).exists or
                shutil.which(self.exe) is not None
            )
        )

    @property
    def cwd(self):
        return self.client.cwd

    def __str__(self):
        return 'Job({}, {}, {})'.format(self.client.name, self.exe, ' '.join(self.args))

    def run(self):
        self.loop.run_until_complete(self.status)

    @property
    def result(self):
        return self.status.result()

    @property
    def success(self):
        return self.status.done() and self.result.success


@contextmanager
def _dummy_ctx():
    yield


class ProcessExecutor(Logging, abc.ABC):
    ''' Handler for subprocess execution
    Because python handles signals only on the main thread and
    subprocess notifcations, like their termination, is noticed by
    catching SIG_CHLD, the actual execution of the coroutines spawning
    the subprocess must be done while the main threads's event loop is
    in the running state, so it can relay the signal to the subprocess's
    event loop.
    As this class can be instantiated and used from within another
    thread's event loop, it is also impossible (afaict) to use either
    that loop or the main thread loop, for proc.wait() thus blocks
    indefinitely with a <defunct> process.
    '''

    def __init__(self, loop=None, main_loop_ctx=_dummy_ctx) -> None:
        self.loop = loop or asyncio.get_event_loop()
        self.main_loop_ctx = main_loop_ctx
        self.current: Map[Any, Job] = Map()

    def process(self, job: Job) -> Awaitable:
        self.log.debug(f'creating subprocess for {job}')
        return asyncio.create_subprocess_exec(
            job.exe,
            *job.args,
            stdin=APIPE,
            stdout=APIPE,
            stderr=APIPE,
            cwd=str(job.cwd),
            loop=self.loop,
            **job.kw,
        )

    async def _execute(self, job: Job):
        def error(msg: str) -> Tuple[int, str, str]:
            return -111, '', msg
        try:
            out, err = None, None
            with self.main_loop_ctx():
                proc = await self.process(job)
                self.log.debug(f'awaiting {job} on the main loop')
                out, err = await proc.communicate(job.stdin)
            if out is None or err is None:
                return error('executing {} failed'.format(job))
            else:
                self.log.debug(f'{job} executed successfully ({out}, {err})')
                return proc.returncode, out.decode(), err.decode()
        except Exception as e:
            self.log.exception(f'{job} failed with {e!r}')
            return error(f'exception: {e}')

    def run(self, job: Job) -> Future[Result]:
        ''' return values of execute are set as result of the task
        returned by ensure_future(), obtainable via task.result()
        '''
        if not self.watcher_ready:
            self.log.error(f'child watcher unattached when executing {job}')
            job.cancel('unattached watcher')
        elif not self.can_execute(job):
            self.log.error('invalid execution job: {}'.format(job))
            job.cancel('invalid')
        else:
            self.log.debug('executing {}'.format(job))
            task = asyncio.ensure_future(self._execute(job), loop=self.loop)
            task.add_done_callback(job.finish)
            task.add_done_callback(L(self.job_done)(job, _))
            self.current[job.client] = job
        return job.status

    @property
    def watcher_ready(self) -> bool:
        with self.main_loop_ctx():
            watcher = asyncio.get_child_watcher()
        return (
            watcher is not None and
            watcher._loop is not None
        )

    def can_execute(self, job: Job):
        return (
            job.client not in self.current and
            job.valid
        )

    def job_done(self, job, status):
        self.log.debug('{} is done with status {}'.format(job, status))
        if job.client in self.current:
            self.current.pop(job.client)

    @property
    def ready(self):
        return self.current.is_empty

    def _run_jobs(self):
        self.current.valmap(lambda job: job.run())

    @property
    def futures(self):
        return self.current.v.map(_.status)

    def await_threadsafe(self, loop):
        async def waiter():
            while not self.ready:
                await asyncio.sleep(0.001)
        loop.run_until_complete(waiter())


class NvimProcessExecutor(ProcessExecutor):

    def __init__(self, vim: NvimApi, loop=None) -> None:
        self.vim = vim
        super().__init__(loop, self._main_event_loop)

    def _main_event_loop(self):
        return self.vim.threadsafe_subprocess() if ribosome.in_vim else _dummy_ctx()


A = TypeVar('A')


class SubprocessResult(Generic[A], Dat['SubprocessResult']):

    def __init__(self, retval: int, stdout: List[str], stderr: List[str], data: A) -> None:
        self.retval = retval
        self.stdout = stdout
        self.stderr = stderr
        self.data = data

    @property
    def success(self) -> Boolean:
        return Boolean(self.retval == 0)


class Subprocess(Generic[A], Dat['Subprocess']):

    @staticmethod
    @do(IO[Tuple[int, List[str], List[str]]])
    def popen(*args: str, timeout: float=None, stdin: int=PIPE, stdout: int=PIPE, stderr: int=PIPE, env: dict=dict(),
              universal_newlines=True, **kw: Any) -> Do:
        log.debug(f'executing subprocess `{args}`')
        pop = yield IO.delay(Popen, args, stdin=stdin, stdout=stdout, stderr=stderr, env=env,
                             universal_newlines=universal_newlines, **kw)
        out, err = yield IO.delay(pop.communicate, timeout=timeout)
        out_lines = Lists.lines(out or '')
        err_lines = Lists.lines(err or '')
        yield IO.pure((-1 if pop.returncode is None else pop.returncode, out_lines, err_lines))

    def __init__(self, exe: Path, args: List[str], data: A, timeout: float, **kw: Any) -> None:
        self.exe = exe
        self.args = args
        self.data = data
        self.timeout = timeout
        self.kw = kw

    @property
    def args_tuple(self) -> tuple:
        return tuple(self.args.cons(str(self.exe)))

    @do(IO[SubprocessResult[A]])
    def execute(self, **kw: Any) -> Do:
        retval, out, err = yield Subprocess.popen(*self.args_tuple, timeout=self.timeout, **kw, **self.kw)
        yield IO.pure(SubprocessResult(retval, out, err, self.data))


__all__ = ('ProcessExecutor', 'Result', 'Job', 'NvimProcessExecutor', 'Subprocess')
