import inspect
from typing import Callable, Any, Tuple, get_type_hints

from amino import Maybe, _, Just, Boolean, Lists, Nothing, Either, L, List, Nil, Map, Left
from amino.dat import Dat
from amino.state import StateT
from amino.util.tpe import first_type_arg, type_arg, is_subclass

from ribosome.rpc.data.nargs import Nargs


def analyse_state_type(tpe: type) -> Tuple[Either[str, type], Either[str, type]]:
    return (
        (first_type_arg(tpe), type_arg(tpe, 1))
        if tpe is not None and is_subclass(tpe, StateT)
        else (Left('not a StateT'), Left('not a StateT'))
    )


def analyse_return_type(fun: Callable[..., Any], hints: Map[str, type]
                        ) -> Tuple[type, Either[str, type], Either[str, type]]:
    main_rettype = getattr(fun, 'tpe', hints.lift('return') | None)
    state_type, return_type = analyse_state_type(main_rettype)
    return main_rettype, state_type, return_type


def cons_params_spec(fun: Callable[..., Any]) -> None:
    argspec = inspect.getfullargspec(fun)
    hints = Map(get_type_hints(fun))
    params = Lists.wrap(argspec.args)
    defaults = Lists.wrap(argspec.defaults or ())
    method = Boolean(params.head.contains('self'))
    param_count = params.length - method.to_int
    min = param_count - defaults.length
    max = (~Boolean(argspec.varargs or argspec.varkw)).m(param_count)
    nargs = Nargs.cons(min, max)
    types = params.traverse(hints.lift, Maybe) | Nil
    main_rettype, state_type, return_type = analyse_return_type(fun, hints)
    return ParamsSpec(nargs, min, max, method, types, main_rettype, state_type, return_type | (lambda: main_rettype))


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
            state_type: Maybe[type],
            return_type: type,
    ) -> None:
        self.nargs = nargs
        self.min = min
        self.max = max
        self.method = method
        self.types = types
        self.rettype = rettype
        self.state_type = state_type
        self.return_type = return_type

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
