from typing import Generic, TypeVar, Tuple

from amino import List, Nil, Lists, Boolean
from amino.dat import Dat, DatMeta

A = TypeVar('A')

Item = Tuple[float, A]
Q = List[Item]


def insert(items: Q, a: A, prio: float) -> Q:
    item = (prio, a)
    index = items.index_where(lambda i: i[0] > prio) | -1
    pre, post = items.take(index), items.drop(index)
    return pre.cat(item) + post


class PrioQueueMeta(DatMeta):

    @property
    def empty(self) -> 'PrioQueue[A]':
        return PrioQueue(Nil)


class PrioQueue(Generic[A], Dat['PrioQueue[A]'], metaclass=PrioQueueMeta):

    def __init__(self, items: Q) -> None:
        self.items = items

    def put(self, a: A, prio: float) -> 'PrioQueue[A]':
        return PrioQueue(Lists.wrap(insert(self.items, a, prio)))

    def put_default(self, a: A) -> 'PrioQueue[A]':
        return self.put(a, 0.5)

    @property
    def get(self) -> 'Either[str, Tuple[PrioQueue[A], A]]':
        return self.items.detach_head.to_either('queue is empty').map2(lambda a, r: (a, PrioQueue(r)))

    @property
    def empty(self) -> Boolean:
        return self.items.empty

__all__ = ('PrioQueue',)
