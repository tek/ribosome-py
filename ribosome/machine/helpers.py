from amino import Map, L, _, List, Left, Right, __

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
        return (name(t)
                if isinstance(name, type) and issubclass(name, VimCallback)
                else name)

    def _inst_callbacks(self, spec, target, special):
        cb = (
            spec /
            L(parse_callback_spec)(_, special) /
            __.flat_map(__.func(self.vim))
        )
        self._callback_errors(spec, cb)
        return cb.filter(_.is_right).join / L(self._inst_callback)(_, target)

    def _callback(self, name, target=None, special=Map()):
        spec = self.options.get(name).o(self.vim.vars.p(name))
        return self._inst_callbacks(spec, target, special)

    def _callbacks(self, name, target=None, special=Map()):
        var = self.vim.vars.pl(name) | List()
        opt = self.options.get(name) | List()
        return self._inst_callbacks(var + opt, target, special)

    def _from_opt(self, tpe, **strict):
        o = self.options ** Map(strict)
        missing = tpe.mandatory_fields.k.filter_not(o.has_key)
        msg = 'cannot create {} without params: {}'
        return (Left(msg.format(tpe, missing)) if missing else
                Right(tpe.from_opt(o)))


__all__ = ('TransitionHelpers',)
