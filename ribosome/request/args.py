import inspect
from typing import Callable, Any

from amino import Maybe, _, Just, Boolean, Lists, Nothing
from amino.dat import Dat

from ribosome.request.nargs import Nargs


class ParamsSpec(Dat['ParamsSpec']):

    @staticmethod
    def from_function(fun: Callable[..., Any]) -> 'ParamsSpec':
        argspec = inspect.getfullargspec(fun)
        params = Lists.wrap(argspec.args)
        defaults = Lists.wrap(argspec.defaults or ())
        method = Boolean(params.head.contains('self'))
        param_count = params.length - method.to_int
        min = param_count - defaults.length
        max = (~Boolean(argspec.varargs or argspec.varkw)).m(param_count)
        nargs = Nargs.cons(min, max)
        return ParamsSpec(nargs, min, max, method)

    def __init__(self, nargs: Nargs, min: int, max: Maybe[int], method: Boolean) -> None:
        self.nargs = nargs
        self.min = min
        self.max = max
        self.method = method

    @property
    def exact_count(self) -> Maybe[int]:
        return Just(self.min) if self.max.contains(self.min) else Nothing


class ArgValidator(Dat['ArgValidator']):

    def __init__(self, spec: ParamsSpec) -> None:
        self.spec = spec

    @property
    def min(self) -> int:
        return self.spec.min

    @property
    def max(self) -> Maybe[int]:
        return self.spec.max

    def validate(self, args: tuple) -> Boolean:
        l = len(args)
        return self.min <= l and not self.max.exists(_ < l)

    def error(self, args: tuple, desc: str, vim_name: str) -> str:
        return f'argument count for {desc} `{vim_name}` is {len(args)}, must be {self.count_spec} ({args})'

    @property
    def count_spec(self) -> str:
        return (
            self.spec.exact_count /
            (lambda a: f'exactly {a}' if a > 0 else 'none') | (
                self.max /
                (lambda mx: f'between {self.min} and {mx}') |
                f'at least {self.min}'
            )
        )

__all__ = ('ArgValidator', 'ParamsSpec')
