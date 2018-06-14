from typing import TypeVar, Callable

from lenses import UnboundLens

from amino import IO, Path, Left, do, Do
from amino.json import decode_json, dump_json
from amino.logging import module_log

from ribosome.nvim.io.compute import NvimIO
from ribosome.nvim.io.state import NS
from ribosome.nvim.io.api import N
from ribosome.config.settings import project_state_dir

log = module_log()
A = TypeVar('A')
D = TypeVar('D')


def mkdir(dir: Path) -> IO[None]:
    return IO.delay(dir.mkdir, parents=True, exist_ok=True)


@do(NvimIO[Path])
def state_file(name: str) -> Do:
    dir = yield project_state_dir.value_or_default()
    yield N.from_io(mkdir(dir))
    yield N.pure(dir / f'{name}.json')


@do(NvimIO[A])
def load_json_data_from(name: str, file: Path) -> Do:
    exists = yield N.from_io(IO.delay(file.exists))
    if exists:
        json = yield N.from_io(IO.delay(file.read_text))
        yield N.pure(decode_json(json))
    else:
        yield N.pure(Left(f'state file {file} does not exist'))


@do(NvimIO[A])
def load_json_data(name: str) -> Do:
    file = yield state_file(name)
    yield load_json_data_from(name, file)


@do(NS[D, None])
def load_json_state(name: str, store: UnboundLens) -> Do:
    state = yield NS.lift(load_json_data(name))
    yield state.cata(lambda a: NS.pure(None), lambda d: NS.modify(store.set(d)))


@do(NvimIO[None])
def store_json_data(name: str, data: A) -> Do:
    file = yield state_file(name)
    json = yield N.from_either(dump_json(data))
    yield N.from_io(IO.delay(file.write_text, json))
    yield N.pure(None)


@do(NS[D, None])
def store_json_state(name: str, fetch: Callable[[D], A]) -> Do:
    payload = yield NS.inspect(fetch)
    yield NS.lift(store_json_data(name, payload))


__all__ = ('load_json_state', 'store_json_data', 'store_json_state')
