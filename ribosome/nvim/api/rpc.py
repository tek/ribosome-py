from typing import Tuple, Any

from amino import _, Either, Map, Left, Right, do, Do

from ribosome.nvim import NvimIO


def plugin_name() -> NvimIO[str]:
    return NvimIO.delay(_.name)


def api_info() -> NvimIO[Tuple[int, dict]]:
    def cons(data: Any) -> Either[str, Tuple[int, Map[str, Any]]]:
        return (
            Left(f'not a tuple: {data}')
            if not isinstance(data, (list, tuple)) else
            Left(f'invalid tuple size: {data}')
            if not len(data) == 2 else
            Left(f'channel is not an int: {data}')
            if not isinstance(data[0], int) else
            Left(f'metadata is not a dict: {data}')
            if not isinstance(data[1], dict) else
            Right(data).map2(lambda a, b: (a, Map(b)))
        )
    return NvimIO.read_cons('nvim_get_api_info', cons)


@do(NvimIO[int])
def channel_id() -> Do:
    channel, metadata = yield api_info()
    return channel


__all__ = ('plugin_name', 'api_info', 'channel_id')
