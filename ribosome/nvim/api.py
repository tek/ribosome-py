from typing import Any, Type, TypeVar, Callable, List as TList

from msgpack import ExtType

from amino import Right, Left, Either, Dat, List, Lists, __, do, Do

from ribosome.nvim import NvimIO

A = TypeVar('A')
B = TypeVar('B')


class Tabpage(Dat['Tabpage']):

    def __init__(self, data: ExtType) -> None:
        self.data = data


class Window(Dat['Window']):

    def __init__(self, data: ExtType) -> None:
        self.data = data


class Buffer(Dat['Buffer']):

    def __init__(self, data: ExtType) -> None:
        self.data = data


def cons_checked(tpe: Type[A], cons: Callable[[A], B]) -> Callable[[Any], Either[str, B]]:
    def cons_data(data: Any) -> Either[str, A]:
        return Right(cons(data)) if isinstance(data, tpe) else Left(f'invalid nvim data for `{tpe}`: {data}')
    return cons_data


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


def current_tabpage() -> NvimIO[Tabpage]:
    return NvimIO.read_tpe('nvim_get_current_tabpage', cons_ext(Tabpage))


def current_window() -> NvimIO[Window]:
    return NvimIO.read_cons('nvim_get_current_win', cons_ext(Window))


def current_buffer() -> NvimIO[Buffer]:
    return NvimIO.read_cons('nvim_get_current_buf', cons_ext(Buffer))


def tabpages() -> NvimIO[List[Tabpage]]:
    return NvimIO.read_cons('nvim_list_bufs', cons_ext_list(Tabpage))


def windows() -> NvimIO[List[Window]]:
    return NvimIO.read_cons('nvim_list_wins', cons_ext_list(Window))


def buffers() -> NvimIO[List[Buffer]]:
    return NvimIO.read_cons('nvim_list_bufs', cons_ext_list(Buffer))


def window_buffer(window: Window) -> NvimIO[Buffer]:
    return NvimIO.read_cons('nvim_win_get_buf', cons_ext(Buffer), window.data)


def set_buffer_lines(
        buffer: Buffer,
        start: int,
        end: int,
        lines: List[str],
        strict_indexing: bool=False,
) -> NvimIO[None]:
    return NvimIO.write('nvim_buf_set_lines', buffer.data, start, end, strict_indexing, lines)


def set_buffer_content(buffer: Buffer, lines: List[str]) -> NvimIO[None]:
    return set_buffer_lines(buffer, 0, -1, lines, False)


def buffer_lines(
        buffer: Buffer,
        start: int,
        end: int,
        strict_indexing: bool=False,
) -> NvimIO[None]:
    return NvimIO.read_cons(
        'nvim_buf_get_lines',
        cons_checked_list(bytes, __.decode()),
        buffer.data,
        start,
        end,
        strict_indexing,
    )


def buffer_content(buffer: Buffer) -> NvimIO[List[str]]:
    return buffer_lines(buffer, 0, -1, False)


@do(NvimIO[List[str]])
def current_buffer_content() -> Do:
    buffer = yield current_buffer()
    yield buffer_content(buffer)


def set_buffer_option(buffer: Buffer, key: str, value: Any) -> NvimIO[None]:
    return NvimIO.write('nvim_buf_set_option', buffer.data, key, value)


__all__ = ('request', 'current_window', 'current_tabpage', 'buffers', 'current_buffer', 'tabpages', 'windows',
           'window_buffer', 'set_buffer_lines', 'set_buffer_content', 'buffer_lines', 'buffer_content',
           'set_buffer_option', 'current_buffer_content')
