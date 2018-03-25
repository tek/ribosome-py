from amino.io import IOExceptionBase
from amino import Maybe, List, Just
from amino.util.trace import default_internal_packages


class NvimIOException(IOExceptionBase):

    @property
    def desc(self) -> str:
        return 'NvimIO exception'

    @property
    def internal_packages(self) -> Maybe[List[str]]:
        return Just(default_internal_packages.cons('ribosome.nvim'))


__all__ = ('NvimIOException',)
