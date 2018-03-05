import inspect
from typing import Callable, Any

from amino import Maybe, _, Just, Boolean, Lists, Nothing, Either, L, List, Nil, Map
from amino.dat import Dat
from amino.state import StateT

from ribosome.request.nargs import Nargs


def cons_params_spec(fun: Callable[..., Any]) -> None:
    argspec = inspect.getfullargspec(fun)
    annotations = Map(argspec.annotations)
    params = Lists.wrap(argspec.args)
    defaults = Lists.wrap(argspec.defaults or ())
    method = Boolean(params.head.contains('self'))
    param_count = params.length - method.to_int
    min = param_count - defaults.length
    max = (~Boolean(argspec.varargs or argspec.varkw)).m(param_count)
    nargs = Nargs.cons(min, max)
    types = params.traverse(annotations.lift, Maybe) | Nil
    rettype = getattr(fun, 'tpe', annotations.lift('return') | None)
    state_type = (
        Maybe.getattr(rettype, '__args__') / Lists.wrap // _.head
        if rettype is not None and issubclass(rettype, StateT)
        else Nothing
    )
    return ParamsSpec(nargs, min, max, method, types, rettype, state_type)


class ParamsSpec(Dat['ParamsSpec']):

    @staticmethod
    def from_function(fun: Callable[..., Any]) -> 'ParamsSpec':
        f = getattr(fun, '__wrapped__', fun)
        return cons_params_spec(f)

    @staticmethod
    def from_type(tpe: type) -> 'ParamsSpec':
        return cons_params_spec(tpe.__init__)

    def __init__(
            self,
            nargs: Nargs,
            min: int,
            max: Maybe[int],
            method: Boolean,
            types: List[type],
            rettype: type,
            state_type: type,
    ) -> None:
        self.nargs = nargs
        self.min = min
        self.max = max
        self.method = method
        self.types = types
        self.rettype = rettype
        self.state_type = state_type

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

    def validate(self, count: int) -> Boolean:
        return Boolean(self.min <= count and not self.max.exists(_ < count))

    def error(self, args: tuple, desc: str, name: str) -> str:
        return f'argument count for {desc} `{name}` is {len(args)}, must be {self.count_spec} ({args})'

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

    def either(self, args: tuple, desc: str, name: str) -> Either[str, None]:
        return self.validate(len(args)).e(L(self.error)(args, desc, name), None)

__all__ = ('ArgValidator', 'ParamsSpec')
