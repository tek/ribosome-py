from amino.logging import LogError

from ribosome.trans.message_base import pmessage, json_pmessage, Message

Nop = pmessage('Nop')
Stop = pmessage('Stop')
Quit = pmessage('Quit')
Done = pmessage('Done')
PlugCommand = pmessage('PlugCommand', 'plug', 'msg')
Info = pmessage('Info', 'message')
ShowLogInfo = pmessage('ShowLogInfo')
RunIOsParallel = pmessage('RunIOsParallel', 'ios')
RunCorosParallel = pmessage('RunCorosParallel', 'coros')
SubProcessSync = pmessage('SubProcessSync', 'job', 'result')
SubProcessAsync = pmessage('SubProcessAsync', 'job', 'result')
Fork = pmessage('Fork', 'callback')
Warning = pmessage('Warning', 'message')
Debug = pmessage('Debug', 'message')
Coroutine = pmessage('Coroutine', 'coro')
CoroutineAlg = pmessage('CoroutineAlg', 'coro')
TransitionException = pmessage('TransitionException', 'context', 'exc')
UpdateRecord = json_pmessage('UpdateRecord', 'tpe', 'name')
UpdateComponentState = json_pmessage('UpdateComponentState', 'tpe', 'name')
Stage1 = pmessage('Stage1')
Stage2 = pmessage('Stage2')
Stage3 = pmessage('Stage3')
Stage4 = pmessage('Stage4')


class Error(Message['Error'], LogError):

    def __init__(self, main, prefix='') -> None:
        self.main = main
        self.prefix = prefix

    @property
    def message(self) -> str:
        pre = f'{self.prefix}: ' if self.prefix else ''
        return f'{pre}{self.main}'

    @property
    def full(self) -> str:
        return self.message

    @property
    def short(self) -> str:
        return self.main

__all__ = ('Nop', 'Stop', 'Quit', 'Done', 'Done', 'PlugCommand', 'Info', 'ShowLogInfo', 'RunIOsParallel',
           'RunCorosParallel', 'SubProcessSync', 'SubProcessAsync', 'Fork', 'Error', 'Warning', 'Debug', 'Coroutine',
           'CoroutineAlg', 'TransitionException', 'UpdateRecord', 'UpdateComponentState', 'Stage1', 'Stage2', 'Stage3',
           'Stage4')
