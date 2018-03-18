from typing import Any, Type, TypeVar, Callable, List as TList, Tuple

from msgpack import ExtType, unpackb

from amino import Right, Left, Either, Dat, List, Lists, __, do, Do, Path, Maybe, Just, Nothing, Try

from ribosome.nvim import NvimIO
from ribosome.nvim.io import nvim_request

A = TypeVar('A')
B = TypeVar('B')


def nvim_command(cmd: str, *args: Any) -> NvimIO[None]:
    arg_string = ' '.join(map(str, args))
    return NvimIO.write('nvim_command', f'silent! {cmd} {arg_string}')


def nvim_command_output(cmd: str, *args: Any) -> NvimIO[None]:
    arg_string = ' '.join(map(str, args))
    return NvimIO.read_cons('nvim_command_output', cons_decode_str, f'{cmd} {arg_string}')


def nvim_call_function(fun: str, *args: Any) -> NvimIO[Any]:
    return nvim_request('nvim_call_function', fun, args)


def nvim_call_tpe(tpe: Type[A], fun: str, *args: Any) -> NvimIO[A]:
    return NvimIO.read_tpe('nvim_call_function', tpe, fun, args)


def nvim_call_cons(cons: Callable[[Any], Either[str, A]], fun: str, *args: Any) -> NvimIO[A]:
    return NvimIO.read_cons('nvim_call_function', cons, fun, args)


class Tabpage(Dat['Tabpage']):

    def __init__(self, data: ExtType) -> None:
        self.data = data


class Window(Dat['Window']):

    def __init__(self, data: ExtType) -> None:
        self.data = data


class Buffer(Dat['Buffer']):

    def __init__(self, data: ExtType) -> None:
        self.data = data


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


cons_decode_str = cons_checked_e(bytes, (lambda a: Try(a.decode)))


def check_str_list(a: list) -> Either[str, List[str]]:
    return Lists.wrap(a).traverse(cons_decode_str, Either)


cons_decode_str_list = cons_checked_e(list, check_str_list)


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


def send_input(data: str) -> NvimIO[None]:
    return NvimIO.write('nvim_input', data)


def buffer_number(buffer: Buffer) -> NvimIO[int]:
    return NvimIO.delay(lambda v: unpackb(buffer.data.data))


@do(NvimIO[None])
def close_buffer(buffer: Buffer) -> Do:
    yield NvimIO.pure(None)
    num = yield buffer_number(buffer)
    yield nvim_command('bdelete', num)


@do(NvimIO[None])
def close_current_buffer() -> Do:
    buffer = yield current_buffer()
    yield close_buffer(buffer)


def extract_int_pair(data: list) -> Either[str, Tuple[int, int]]:
    data_l = Lists.wrap(data)
    @do(Maybe[Tuple[int, int]])
    def run() -> Do:
        first = yield data_l.lift(0)
        second = yield data_l.lift(1)
        yield Just((first, second)) if isinstance(first, int) and isinstance(second, int) else Nothing
    return run().to_either(lambda: f'invalid nvim data for int pair: {data}')


def cursor(window: Window) -> NvimIO[Tuple[int, int]]:
    return NvimIO.read_cons('nvim_win_get_cursor', cons_checked_e(list, extract_int_pair), window.data)


@do(NvimIO[Tuple[int, int]])
def current_cursor() -> Do:
    window = yield current_window()
    yield cursor(window)


@do(NvimIO[int])
def window_line(window: Window) -> Do:
    line, col = yield cursor(window)
    return line


def focus_window(window: Window) -> NvimIO[None]:
    return NvimIO.write('nvim_set_current_win', window.data)


def edit_file(file: Path) -> NvimIO[None]:
    return nvim_command('edit', str(file))


def buffer_name(buffer: Buffer) -> NvimIO[str]:
    return NvimIO.read_cons('nvim_buf_get_name', cons_checked(bytes, __.decode()), buffer.data)


@do(NvimIO[str])
def window_buffer_name(window: Window) -> Do:
    buffer = yield window_buffer(window)
    yield buffer_name(buffer)


@do(NvimIO[str])
def current_buffer_name() -> Do:
    buffer = yield current_buffer()
    yield buffer_name(buffer)


def set_cursor(window: Window, coords: Tuple[int, int]) -> NvimIO[None]:
    line, col = coords
    return NvimIO.write('nvim_win_set_cursor', window.data, coords)


def set_line(window: Window, line: int) -> NvimIO[None]:
    return set_cursor(window, (line, 0))


@do(NvimIO[None])
def set_local_cursor(coords: Tuple[int, int]) -> Do:
    window = yield current_window()
    yield set_cursor(window, coords)


@do(NvimIO[int])
def current_window_number() -> Do:
    window = yield current_window()
    yield NvimIO.read_tpe('nvim_win_get_number', int, window.data)


def define_function(name: str, params: List[str], body: str) -> NvimIO[None]:
    return nvim_command_output(f'function!', f'{name}({params.join_comma})\n{body}\nendfunction')


__all__ = ('current_window', 'current_tabpage', 'buffers', 'current_buffer', 'tabpages', 'windows', 'window_buffer',
           'set_buffer_lines', 'set_buffer_content', 'buffer_lines', 'buffer_content', 'set_buffer_option',
           'current_buffer_content', 'cursor', 'window_line', 'focus_window', 'edit_file', 'buffer_name',
           'current_buffer_name', 'set_cursor', 'set_local_cursor', 'set_line', 'window_buffer_name',
           'current_window_number', 'nvim_call_function', 'nvim_command_output')
