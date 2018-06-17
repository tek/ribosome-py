import time
from typing import Callable, TypeVar, Type, Any, List as TList, Tuple

from msgpack import ExtType

from amino import Either, Left, Right, List, Lists, Try, do, Maybe, Do, Just, Nothing
from amino.json import decode_json
from amino.json.decoder import decode_json_type

from ribosome.nvim.io.compute import NvimIO, lift_n_result
from ribosome.nvim.io.api import N
from ribosome.nvim.io.data import NResult, NSuccess

A = TypeVar('A')
B = TypeVar('B')


def cons_checked_e(tpe: Type[A], cons: Callable[[A], Either[str, B]]) -> Callable[[Any], Either[str, B]]:
    def cons_data(data: Any) -> Either[str, A]:
        return cons(data) if isinstance(data, tpe) else Left(f'invalid nvim data for `{tpe}`: {data}')
    return cons_data


def cons_checked(tpe: Type[A], cons: Callable[[A], B]) -> Callable[[Any], Either[str, B]]:
    return cons_checked_e(tpe, lambda a: Right(cons(a)))


def cons_ext(cons: Callable[[ExtType], A]) -> Callable[[Any], Either[str, A]]:
    return cons_checked(ExtType, cons)


def cons_checked_list_e(tpe: Type[A], cons: Callable[[A], Either[str, B]]) -> Callable[[Any], Either[str, List[B]]]:
    def cons_data(data: Any) -> Either[str, List[B]]:
        return (
            Lists.wrap(data).traverse(cons_checked_e(tpe, cons), Either)
            if isinstance(data, TList) else
            Left(f'invalid nvim data for `List[{tpe}]`: {data}')
        )
    return cons_data


def cons_checked_list(tpe: Type[A], cons: Callable[[A], B]) -> Callable[[Any], Either[str, List[B]]]:
    return cons_checked_list_e(tpe, lambda a: Right(cons(a)))


def cons_ext_list(cons: Callable[[ExtType], A]) -> Callable[[Any], Either[str, List[A]]]:
    return cons_checked_list(ExtType, cons)


cons_decode_str = cons_checked_e((bytes, str), (lambda a: Try(a.decode) if isinstance(a, bytes) else Right(a)))


def check_str_list(a: list) -> Either[str, List[str]]:
    return Lists.wrap(a).traverse(cons_decode_str, Either)


cons_decode_str_list = cons_checked_e(list, check_str_list)


cons_split_lines = cons_checked(str, Lists.lines)


def check_bool(a: Any) -> Either[str, bool]:
    return Right(a == 1) if a == 1 or a == 0 else Left(f'nvim result is not a boolean: {a}')


cons_decode_bool = cons_checked_e(int, check_bool)


def extract_int_pair(data: list) -> Either[str, Tuple[int, int]]:
    data_l = Lists.wrap(data)
    @do(Maybe[Tuple[int, int]])
    def run() -> Do:
        first = yield data_l.lift(0)
        second = yield data_l.lift(1)
        yield Just((first, second)) if isinstance(first, int) and isinstance(second, int) else Nothing
    return run().to_either(lambda: f'invalid nvim data for int pair: {data}')


def split_option(value: str) -> List[str]:
    return Lists.split(value, ',')


cons_decode_str_list_option = cons_checked(str, split_option)

cons_json = cons_checked_e(str, decode_json)


def cons_json_tpe(tpe: Type[A]) -> NvimIO[A]:
    return cons_checked_e(str, lambda a: decode_json_type(a, tpe))


@do(NvimIO[A])
def nvimio_repeat_timeout(
        thunk: Callable[[], NvimIO[A]],
        check: Callable[[A], bool],
        error: str,
        timeout: float,
        interval: float=None,
) -> Do:
    effective_interval = .01 if interval is None else interval
    start = yield N.simple(time.time)
    @do(NvimIO[None])
    def wait_and_recurse() -> Do:
        yield N.sleep(effective_interval)
        yield recurse()
    @do(NvimIO[None])
    def recurse() -> Do:
        result = yield thunk()
        done = check(result)
        yield (
            N.pure(result)
            if done else
            N.error(error)
            if time.time() - start > timeout else
            wait_and_recurse()
        )
    yield recurse()


def nvimio_result(thunk: Callable[..., NvimIO[A]], *a: Any, **kw: Any) -> NvimIO[NResult[A]]:
    return N.intercept(thunk(*a, **kw), N.pure)


@do(NvimIO[A])
def nvimio_await_success(
        thunk: Callable[..., NvimIO[A]],
        timeout: float,
        *a: Any,
        interval: float=.01,
        **kw: Any,
) -> Do:
    start = yield N.simple(time.time)
    @do(NvimIO[None])
    def wait_and_recurse() -> Do:
        yield N.sleep(interval)
        yield recurse()
    @do(NvimIO[None])
    def recurse() -> Do:
        result = yield nvimio_result(thunk, *a, **kw)
        yield (
            lift_n_result.match(result)
            if isinstance(result, NSuccess) or time.time() - start > timeout else
            wait_and_recurse()
        )
    yield recurse()


def format_bufdo(cmd: str, start: int, end: Maybe[int]) -> str:
    range = end.map(lambda a: f'{start},{a}').get_or(str, start)
    return f'{range}bufdo {cmd}'


def format_windo(cmd: str, start: int, end: Maybe[int]) -> str:
    range = end.map(lambda a: f'{start},{a}').get_or(str, start)
    return f'{range}windo {cmd}'


__all__ = ('cons_checked_e', 'cons_checked', 'cons_ext', 'cons_checked_list', 'cons_ext_list', 'check_str_list',
           'cons_decode_str', 'cons_decode_str_list', 'extract_int_pair', 'split_option', 'cons_decode_str_list_option',
           'cons_split_lines', 'cons_decode_bool', 'nvimio_repeat_timeout', 'cons_json', 'cons_json_tpe',
           'nvimio_await_success', 'cons_checked_list_e', 'format_bufdo', 'format_windo',)
