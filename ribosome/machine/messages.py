from amino import Nothing
from amino.logging import LogError

from ribosome.machine.message_base import message, Message, json_message

Nop = message('Nop')
Stop = message('Stop')
Quit = message('Quit')
Done = message('Done')
PlugCommand = message('PlugCommand', 'plug', 'msg')
RunNvimIO = message('RunNvimIO', 'io')
RunNvimUnitIO = message('RunNvimUnitIO', 'io')
RunIO = message('RunIO', 'io', opt_fields=(('msg', Nothing),))
RunIOAlg = message('RunIOAlg', 'io', opt_fields=(('msg', Nothing),))
RunNvimIOAlg = message('RunNvimIOAlg', 'io')
UnitIO = message('UnitIO', 'io', opt_fields=(('msg', Nothing),))
DataIO = message('DataIO', 'cons', opt_fields=(('msg', Nothing),))
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
Stage1 = message('Stage1')
Stage2 = message('Stage2')
Stage3 = message('Stage3')
Stage4 = message('Stage4')


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

__all__ = ('Nop', 'Stop', 'Quit', 'Done', 'Done', 'PlugCommand', 'RunNvimIO', 'RunNvimUnitIO', 'UnitIO', 'DataIO',
           'ShowLogInfo', 'RunIOsParallel', 'RunCorosParallel', 'SubProcessSync', 'RunIO', 'RunIOAlg',
           'RunNvimIOAlg', 'Error', 'Warning', 'Debug', 'Coroutine', 'TransitionException', 'Info', 'UpdateRecord',
           'UpdateState', 'Stage1', 'Stage2', 'Stage3', 'Stage4')
