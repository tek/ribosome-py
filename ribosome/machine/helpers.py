from amino import Map, L, _, List, Left, Right

from ribosome.util.callback import VimCallback, parse_callback_spec


class TransitionHelpers:

    @property
    def options(self):
        return Map()

    def _callback_errors(self, spec, cb):
        def log(s, e):
            self.log.error('failed to parse callback \'{}\': {}'.format(s, e))
        (spec.zip(cb)).map2(lambda s, c: c.lmap(L(log)(s, _)))

    def _inst_callback(self, name, target):
        t = target or self.vim
        return name(t) if issubclass(name, VimCallback) else name

    def _inst_callbacks(self, spec, target):
        cb = spec / parse_callback_spec / _.join
        self._callback_errors(spec, cb)
        return cb.filter(_.is_right).join / L(self._inst_callback)(_, target)

    def _callback(self, name, target=None):
        spec = self.options.get(name).o(self.vim.vars.p(name))
        return self._inst_callbacks(spec, target)

    def _callbacks(self, name, target=None):
        t = target or self.vim
        def inst(name):
            return name(t) if issubclass(name, VimCallback) else name
        var = self.vim.vars.pl(name) | List()
        opt = self.options.get(name) | List()
        return self._inst_callbacks(var + opt, target)

    def _from_opt(self, tpe, **strict):
        o = self.options ** Map(strict)
        missing = tpe.mandatory_fields.k.filter_not(o.has_key)
        msg = 'cannot create {} without params: {}'
        return (Left(msg.format(tpe, missing)) if missing else
                Right(tpe.from_opt(o)))


__all__ = ('TransitionHelpers',)
