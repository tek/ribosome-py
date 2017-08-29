import abc

from amino import Nothing
from amino.logging import LogError

from ribosome.machine.message_base import message, Message, json_message

Nop = message('Nop')
Stop = message('Stop')
Quit = message('Quit')
Done = message('Done')
PlugCommand = message('PlugCommand', 'plug', 'msg')
NvimIOTask = message('NvimIOTask', 'io')
RunTask = message('RunTask', 'task', opt_fields=(('msg', Nothing),))
RunIO = RunTask
RunIOAlg = message('RunIOAlg', 'io', opt_fields=(('msg', Nothing),))
RunNvimIO = message('RunNvimIO', 'io')
RunNvimIOAlg = message('RunNvimIOAlg', 'io')
UnitTask = message('UnitTask', 'task', opt_fields=(('msg', Nothing),))
DataTask = message('DataTask', 'cons', opt_fields=(('msg', Nothing),))
Info = message('Info', 'message')
ShowLogInfo = message('ShowLogInfo')
RunIOsParallel = message('RunIOsParallel', 'ios')
RunCorosParallel = message('RunCorosParallel', 'coros')
SubProcessSync = message('SubProcessSync', 'job', 'result')
Warning = message('Warning', 'message')
Debug = message('Debug', 'message')
Coroutine = message('Coroutine', 'coro')
TransitionException = message('TransitionException', 'context', 'exc')
UpdateRecord = json_message('UpdateRecord', 'tpe', 'name')
UpdateState = json_message('UpdateState', 'tpe', 'name')


class Error(Message, LogError, fields=('main',), opt_fields=(('prefix', ''),)):

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

__all__ = ('Nop', 'Stop', 'Quit', 'Done', 'Done', 'PlugCommand', 'NvimIOTask', 'RunTask', 'UnitTask', 'DataTask',
           'ShowLogInfo', 'RunIOsParallel', 'RunCorosParallel', 'SubProcessSync', 'RunIO', 'RunIOAlg', 'RunNvimIO',
           'RunNvimIOAlg', 'Error', 'Warning', 'Debug', 'Coroutine', 'TransitionException', 'Info', 'UpdateRecord',
           'UpdateState')
