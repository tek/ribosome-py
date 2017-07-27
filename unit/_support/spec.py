import amino
import amino.test
from amino.logging import amino_stdout_logging
from amino.test.spec_spec import Spec as SpecBase


class Spec(SpecBase):

    def setup(self, *a, **kw):
        amino.development = True
        amino_stdout_logging()
        super(Spec, self).setup(*a, **kw)


__all__ = ('Spec',)
