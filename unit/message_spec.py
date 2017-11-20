from kallikrein import k, Expectation

from ribosome.trans.message_base import pmessage, json_pmessage


Mess = pmessage('Mess')
JMess = json_pmessage('JMess')


class MessageSpec:
    '''
    json repr of messages $json_repr
    '''

    def json_repr(self) -> Expectation:
        mod = self.__module__
        return (
            (k(Mess().json_repr['__type__']) == f'{mod}.Mess') &
            (k(JMess().json_repr['__type__']) == f'{mod}.JMess')
        )

__all__ = ('MessageSpec',)
