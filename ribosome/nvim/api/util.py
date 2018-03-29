import time
from typing import Callable, TypeVar, Type, Any, List as TList, Tuple

from msgpack import ExtType

from amino import Either, Left, Right, List, Lists, Try, do, Maybe, Do, Just, Nothing

from ribosome.nvim.io.compute import NvimIO
from ribosome.nvim.io.api import N

A = TypeVar('A')
B = TypeVar('B')


def run_once_defined(job: Callable[[], NvimIO[A]], err: str, timeout: int=10) -> NvimIO[A]:
    start = time.time()
    def loop() -> NvimIO[A]:
        def recurse(err: Exception) -> NvimIO[A]:
            time.sleep(.1)
            return loop()
        return (
            N.recover_fatal(job(), recurse)
            if time.time() - start < timeout else
            N.error(err)
        )
    return loop()


def cons_checked_e(tpe: Type[A], cons: Callable[[A], Either[str, B]]) -> Callable[[Any], Either[str, B]]:
    def cons_data(data: Any) -> Either[str, A]:
        return cons(data) if isinstance(data, tpe) else Left(f'invalid nvim data for `{tpe}`: {data}')
    return cons_data


def cons_checked(tpe: Type[A], cons: Callable[[A], B]) -> Callable[[Any], Either[str, B]]:
    return cons_checked_e(tpe, lambda a: Right(cons(a)))


def cons_ext(cons: Callable[[ExtType], A]) -> Callable[[Any], Either[str, A]]:
    return cons_checked(ExtType, cons)


def cons_checked_list(tpe: Type[A], cons: Callable[[A], B]) -> Callable[[Any], Either[str, List[B]]]:
    def cons_data(data: Any) -> Either[str, A]:
        return (
            Lists.wrap(data).traverse(cons_checked(tpe, cons), Either)
            if isinstance(data, TList) else
            Left(f'invalid nvim data for `List[{tpe}]`: {data}')
        )
    return cons_data


def cons_ext_list(cons: Callable[[ExtType], A]) -> Callable[[Any], Either[str, List[A]]]:
    return cons_checked_list(ExtType, cons)


cons_decode_str = cons_checked_e((bytes, str), (lambda a: Try(a.decode) if isinstance(a, bytes) else Right(a)))


def check_str_list(a: list) -> Either[str, List[str]]:
    return Lists.wrap(a).traverse(cons_decode_str, Either)


cons_decode_str_list = cons_checked_e(list, check_str_list)


cons_split_lines = cons_checked(str, Lists.lines)


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


__all__ = ('run_once_defined', 'cons_checked_e', 'cons_checked', 'cons_ext', 'cons_checked_list', 'cons_ext_list',
           'check_str_list', 'cons_decode_str', 'cons_decode_str_list', 'extract_int_pair', 'split_option',
           'cons_decode_str_list_option', 'cons_split_lines')
