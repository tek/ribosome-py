from kallikrein import k, Expectation

from ribosome.machine import message, json_message


Mess = message('Mess')
JMess = json_message('JMess')


class MessageSpec:
    '''
    test $test
    '''

    def test(self) -> Expectation:
        mod = self.__module__
        return (
            (k(Mess().json_repr['__type__']) == f'{mod}.Mess') &
            (k(JMess().json_repr['__type__']) == f'{mod}.JMess')
        )

__all__ = ('MessageSpec',)
