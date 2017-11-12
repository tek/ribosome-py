import threading
import subprocess
from subprocess import PIPE
from typing import TypeVar

from ribosome.machine.sub import Component
from ribosome.machine.message_base import pmessage, json_pmessage, Message, ToMachine

from amino.util.string import blue
from amino import Just, Maybe, __, _
from ribosome.machine.transition import may_handle, handle
from ribosome.machine.messages import Nop, Done, Quit, Stop, CoroutineAlg, SubProcessAsync, Fork, Coroutine
from ribosome.machine.handler import AlgResultValidator
from ribosome.machine import trans
from ribosome.data import Data

Callback = pmessage('Callback', 'func')
EnvelopeOld = pmessage('EnvelopeOld', 'message', 'to')
RunMachine = json_pmessage('RunMachine', 'machine')
KillMachine = pmessage('KillMachine', 'uuid')
RunScratchMachine = json_pmessage('RunScratchMachine', 'machine')
Init = pmessage('Init')
IfUnhandled = pmessage('IfUnhandled', 'msg', 'unhandled')
A = TypeVar('A')
D = TypeVar('D', bound=Data)


class Internal(Component):

    @may_handle(Nop)
    def _nop(self):
        pass

    @may_handle(Stop)
    def _stop_msg(self):
        return Quit(), Done().pub.at(1)

    @may_handle(Done)
    def _done_msg(self):
        self._done()

    @may_handle(Callback)
    def message_callback(self):
        return self.msg.func(self.data)

    @may_handle(Coroutine)
    def _couroutine(self):
        return self.msg

    @may_handle(CoroutineAlg)
    def message_couroutine_alg(self):
        async def run_coro_alg() -> None:
            res = await self.msg.coro
            trans_desc = blue(f'{self.name}.message_couroutine_alg')
            return Just(AlgResultValidator(trans_desc).validate(res, self.data))
        return run_coro_alg()

    @trans.one(SubProcessAsync)
    def message_sub_process_async(self) -> None:
        def subproc_async() -> Message:
            job = self.msg.job
            proc = subprocess.run(
                args=job.args.cons(job.exe),
                stdin=PIPE,
                stdout=PIPE,
                stderr=PIPE,
                cwd=str(job.cwd),
                **job.kw,
            )
            self.log.debug(f'finished async subproc with {proc}')
            result = job.result_strict(proc.returncode, proc.stdout or '', proc.stderr or '')
            return self.msg.result(result)
        return Fork(subproc_async)

    @trans.unit(Fork)
    def message_fork(self) -> None:
        def dispatch() -> None:
            try:
                self.msg.callback() % self.send
            except Exception as e:
                self.log.caught_exception(f'running forked function {self.msg.callback}', e)
        threading.Thread(target=dispatch).start()

    @may_handle(RunMachine)
    def message_run_machine(self):
        self.sub = self.sub.cat(self.msg.machine)
        init = self.msg.options.get('init') | Init()
        return EnvelopeOld(init, self.msg.machine.uuid)

    @may_handle(KillMachine)
    def message_kill_machine(self):
        self.sub = self.sub.filter_not(_.uuid == self.msg.uuid)

    @handle(EnvelopeOld)
    def message_envelope(self):
        return self.sub.find(_.uuid == self.msg.to) / __.loop_process(self.data, self.msg.message)

    @handle(ToMachine)
    def message_to_machine(self) -> Maybe:
        return self.sub.find(_.name == self.msg.target) / __.loop_process(self.data, self.msg.message)

    @may_handle(IfUnhandled)
    def if_unhandled(self):
        result = self._send(self.data, self.msg.msg)
        return result if result.handled else self._send(self.data, self.msg.unhandled)

__all__ = ('Internal', 'RunMachine', 'KillMachine', 'RunScratchMachine')
