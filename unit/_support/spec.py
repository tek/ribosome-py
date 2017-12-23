import amino
import amino.test
from amino.logging import amino_stdout_logging
from amino.test.spec_spec import Spec as SpecBase


class Spec(SpecBase):

    def setup(self):
        amino.development = True
        amino_stdout_logging()
        super().setup()


__all__ = ('Spec',)
