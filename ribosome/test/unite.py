from functools import wraps

from amino import env


def unite(f):
    @wraps(f)
    def wrapper(self):
        def go(unite):
            self.vim.options.amend_l('rtp', [unite])
            self.vim.cmd('source {}/plugin/*.vim'.format(unite))
            self.vim.cmd('source {}/plugin/unite/*.vim'.format(unite))
            self.vim.cmd('source {}/syntax/*.vim'.format(unite))
            return f(self, unite)
        env['UNITE_DIR'] % go
    return wrapper

__all__ = ('unite',)
