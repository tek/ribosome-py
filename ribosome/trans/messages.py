from ribosome.trans.message_base import pmessage, json_pmessage

Nop = pmessage('Nop')
Stop = pmessage('Stop')
Done = pmessage('Done')
PlugCommand = pmessage('PlugCommand', 'plug', 'msg')
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

__all__ = ('Nop', 'Stop', 'Done', 'Done', 'PlugCommand', 'ShowLogInfo', 'RunIOsParallel',
           'RunCorosParallel', 'SubProcessSync', 'SubProcessAsync', 'Fork', 'Warning', 'Debug', 'Coroutine',
           'CoroutineAlg', 'TransitionException', 'UpdateRecord', 'UpdateComponentState')
