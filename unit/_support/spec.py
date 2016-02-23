import tryp
import tryp.test
from tryp.logging import tryp_stdout_logging


class Spec(tryp.test.Spec):

    def setup(self, *a, **kw):
        tryp.development = True
        tryp_stdout_logging()
        super(Spec, self).setup(*a, **kw)


__all__ = ['Spec']
