from typing import TypeVar

from ribosome.nvim import NvimIO, NvimFacade

from kallikrein import kf
from kallikrein.expectable import Expectable

A = TypeVar('A')


def kn(io: NvimIO[A], vim: NvimFacade) -> Expectable:
    return kf(io.unsafe, vim)


__all__ = ('kn',)
