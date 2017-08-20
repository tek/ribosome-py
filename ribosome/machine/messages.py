from amino import Nothing

from ribosome.machine.message_base import message

Nop = message('Nop')
Stop = message('Stop')
Quit = message('Quit')
Done = message('Done')
PlugCommand = message('PlugCommand', 'plug', 'msg')
NvimIOTask = message('NvimIOTask', 'io')
RunTask = message('RunTask', 'task', opt_fields=(('msg', Nothing),))
RunIO = RunTask
RunIOAlg = message('RunIOAlg', 'io', opt_fields=(('msg', Nothing),))
UnitTask = message('UnitTask', 'task', opt_fields=(('msg', Nothing),))
DataTask = message('DataTask', 'cons', opt_fields=(('msg', Nothing),))
ShowLogInfo = message('ShowLogInfo')
RunIOsParallel = message('RunIOsParallel', 'ios')
RunCorosParallel = message('RunCorosParallel', 'coros')
SubProcessSync = message('SubProcessSync', 'job', 'result')
Error = message('Error', 'message')
Warning = message('Warning', 'message')
Debug = message('Debug', 'message')
Coroutine = message('Coroutine', 'coro')
TransitionException = message('TransitionException', 'context', 'exc')

__all__ = ('Nop', 'Stop', 'Quit', 'Done', 'Done', 'PlugCommand', 'NvimIOTask', 'RunTask', 'UnitTask', 'DataTask',
           'ShowLogInfo', 'RunIOsParallel', 'RunCorosParallel', 'SubProcessSync', 'RunIO', 'RunIOAlg', 'Error',
           'Warning', 'Debug', 'Coroutine', 'TransitionException')
