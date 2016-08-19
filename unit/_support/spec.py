import amino
import amino.test
from amino.logging import amino_stdout_logging


class Spec(amino.test.Spec):

    def setup(self, *a, **kw):
        amino.development = True
        amino_stdout_logging()
        super(Spec, self).setup(*a, **kw)


__all__ = ['Spec']
