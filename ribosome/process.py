from pathlib import Path
import shutil
from contextlib import contextmanager

import asyncio
from asyncio.subprocess import PIPE

from amino import Map, Future, __, Boolean, F, _
from amino.lazy import lazy
from amino.either import Right, Left

import ribosome
from ribosome.logging import Logging
from ribosome.nvim import NvimFacade
from ribosome.record import Record, any_field, field, list_field, maybe_field


class Result(object):

    def __init__(self, job: 'Job', success: bool, out: str, err: str) -> None:
        self.job = job
        self.success = Boolean(success)
        self.out = out
        self.err = err

    def __str__(self):
        return ('subprocess finished successfully'
                if self.success
                else 'subprocess failed: {} ({})'.format(self.msg, self.job))

    def __repr__(self):
        return '{}({}, {}, {})'.format(self.__class__.__name__, self.job,
                                       self.success, self.msg)

    @property
    def msg(self):
        return self.err if self.err else self.out

    def either(self, good, bad):
        return self.success.maybe(Right(good)) | Left(bad)


class JobClient(Record):
    cwd = field(Path)
    name = field(str)


class Job(Record):
    client = field(JobClient)
    exe = field(str)
    args = list_field()
    loop = any_field()
    pipe_in = maybe_field(str)

    @lazy
    def status(self):
        return Future(loop=self.loop)

    @lazy
    def stdin(self):
        return self.pipe_in.map(__.encode()) | None

    def finish(self, f):
        code, out, err = f.result()
        self.status.set_result(Result(self, code == 0, out, err))

    def cancel(self, reason: str):
        self.status.set_result(
            Result(self, False, '', 'canceled: {}'.format(reason)))

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
        return 'Job({}, {}, {})'.format(self.client.name, self.exe,
                                        ' '.join(self.args))

    def run(self):
        self.loop.run_until_complete(self.status)

    @property
    def result(self):
        return self.status.result()

    @property
    def success(self):
        return self.status.done() and self.result.success


class ProcessExecutor(Logging):
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

    def __init__(self, vim: NvimFacade, loop=None) -> None:
        self.vim = vim
        self.loop = loop or asyncio.get_event_loop()
        self.current = Map()  # type: Map[Any, Job]

    async def process(self, job: Job):
        return await asyncio.create_subprocess_exec(
            job.exe,
            *job.args,
            stdin=PIPE,
            stdout=PIPE,
            stderr=PIPE,
            cwd=str(job.cwd),
            loop=self.loop,
        )

    async def _execute(self, job: Job):
        try:
            with self._main_event_loop():
                proc = await self.process(job)
                (out, err) = await proc.communicate(job.stdin)
            msg = '{} executed successfully ({}, {})'.format(job, out, err)
            self.log.debug(msg)
            return proc.returncode, out.decode(), err.decode()
        except Exception as e:
            self.log.exception('{} failed with {}'.format(job, repr(e)))
            return -111, '', 'exception: {}'.format(e)

    def run(self, job: Job) -> Future[Result]:
        ''' return values of execute are set as result of the task
        returned by ensure_future(), obtainable via task.result()
        '''
        if self._can_execute(job):
            self.log.debug('executing {}'.format(job))
            task = asyncio.ensure_future(self._execute(job), loop=self.loop)
            task.add_done_callback(job.finish)
            task.add_done_callback(F(self.job_done, job))
            self.current[job.client] = job
        else:
            self.log.error('invalid execution job: {}'.format(job))
            job.cancel('invalid')
        return job.status

    def _can_execute(self, job: Job):
        return job.client not in self.current and job.valid

    def job_done(self, job, status):
        self.log.debug('{} is done with status {}'.format(job, status))
        if job.client in self.current:
            self.current.pop(job.client)

    @property
    def ready(self):
        return self.current.is_empty

    def _main_event_loop(self):
        return (self.vim.main_event_loop() if ribosome.in_vim else
                self._dummy_ctx())

    @contextmanager
    def _dummy_ctx(self):
        yield

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

__all__ = ('ProcessExecutor', 'Result', 'Job')
