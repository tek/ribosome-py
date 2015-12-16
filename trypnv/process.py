from typing import Tuple, Callable, Any
from pathlib import Path
import shutil
import threading

from fn import F, _  # type: ignore

import asyncio
from asyncio.subprocess import PIPE  # type: ignore

from tryp import Map, List, Future

import trypnv
from trypnv.logging import Logging
from trypnv.nvim import NvimFacade


class Result(object):

    def __init__(self, job: 'Job', success: bool, out: str, err: str) -> None:
        self.job = job
        self.success = success
        self.out = out
        self.err = err

    def __str__(self):
        return ('subprocess finished successfully'
                if self.success
                else 'subprocess failed: {} ({})'.format(self.msg, self.job))

    @property
    def msg(self):
        return self.err if self.err else self.out


class Job(object):

    def __init__(
            self,
            owner,
            exe: str,
            args: List[str],
            loop,
    ) -> None:
        self.owner = owner
        self.exe = exe
        self.args = args
        self.loop = loop
        self.status = Future(loop=loop)  # type: Future

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
        return self.owner.root

    def __str__(self):
        return 'Job({}, {}, {})'.format(self.owner.name, self.exe,
                                        ' '.join(self.args))

    def run(self):
        self.loop.run_until_complete(self.status)

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
        self.loop = loop or asyncio.new_event_loop()
        self.current = Map()  # type: Map[Any, Job]

    async def process(self, job: Job):
        return await asyncio.create_subprocess_exec(
            job.exe,
            *job.args,
            stdout=PIPE,
            stderr=PIPE,
            cwd=str(job.cwd),
            loop=self.loop,
        )

    async def _execute(self, job: Job):
        try:
            proc = await self.process(job)
            await proc.wait()
            out = await proc.stdout.read()
            err = await proc.stderr.read()
            msg = '{} executed successfully ({}, {})'.format(job, out, err)
            self.log.verbose(msg)
            return proc.returncode, out.decode(), err.decode()
        except Exception as e:
            self.log.verbose('{} failed with {}'.format(job, e))
            return -111, '', 'exception: {}'.format(e)

    def run(self, job: Job) -> Future[Result]:
        ''' return values of execute are set as result of the task
        returned by ensure_future(), obtainable via task.result()
        '''
        if self._can_execute(job):
            self.log.verbose('executing {}'.format(job))
            task = asyncio.ensure_future(self._execute(job), loop=self.loop)
            task.add_done_callback(job.finish)
            task.add_done_callback(F(self.job_done, job))
            self.current[job.owner] = job
        else:
            self.log.error('invalid execution job: {}'.format(job))
            job.cancel('invalid')
        return job.status

    def _can_execute(self, job: Job):
        return job.owner not in self.current and job.valid

    def job_done(self, job, status):
        self.log.verbose('{} is done with status {}'.format(job, status))
        if job.owner in self.current:
            self.current.pop(job.owner)

    @property
    def ready(self):
        return self.current.is_empty

    def exec(self):
        if trypnv.in_vim:
            with self.vim.main_event_loop():
                self._run_jobs()
        else:
            threading.Thread(target=lambda: self._run_jobs()).start()

    def _run_jobs(self):
        self.current.valmap(lambda job: job.run())

    @property
    def futures(self):
        return self.current.values.map(_.status)

    def await_threadsafe(self, loop):
        async def waiter():
            while not self.ready:
                await asyncio.sleep(0.001)
        loop.run_until_complete(waiter())

__all__ = ['ProcessExecutor', 'Result', 'Job']
