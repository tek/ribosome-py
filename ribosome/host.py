from typing import TypeVar, Type, Callable, Any
from types import ModuleType

from amino import Either, _, L, amino_log, __, Path, Nil, Just, IO, List, do, Do

from amino.either import ImportFailure
from amino.logging import amino_root_file_logging, module_log
from amino.mod import instance_from_module
from amino.json import decode_json
from amino.util.exception import format_exception
from amino.test.time import timed

from ribosome.config.config import Config
from ribosome.rpc.uv.uv import start_uv_plugin_sync

log = module_log()
D = TypeVar('D')
DIO = TypeVar('DIO')
B = TypeVar('B')
CC = TypeVar('CC')
R = TypeVar('R')


def report_runtime_error(result: Any) -> int:
    amino_log.error(f'error in plugin execution: {result}')
    return 1


def run_loop_uv(config: Config) -> int:
    amino_log.debug(f'starting plugin from {config.basic}')
    result = start_uv_plugin_sync(config).attempt
    return result.cata(report_runtime_error, lambda a: 0)


def config_from_module(mod: ModuleType) -> Either[str, Type[Config]]:
    return instance_from_module(mod, Config)


log_initialized = False


def error(msg: str) -> int:
    try:
        amino_log.error(msg)
    except Exception as e:
        pass
    return 1


def import_error(e: ImportFailure, desc: str) -> int:
    return error(e.expand.join_lines)


def exception(e: Exception, desc: str) -> int:
    f = __.caught_exception_error(f'starting host from {desc}', e)
    try:
        f(amino_log)
    except Exception as e:
        pass
    return 1


def start_module_config(mod: ModuleType) -> int:
    return config_from_module(mod).cata(error, run_loop_uv)


def setup_log() -> None:
    amino_root_file_logging()


def start_from(source: str, importer: Callable[[str], Either[ImportFailure, ModuleType]], desc: str) -> int:
    try:
        setup_log()
        amino_log.debug(f'start_{desc}: {source}')
        return importer(source).cata(L(import_error)(_, source), start_module_config)
    except Exception as e:
        return exception(e, source)


def start_module(mod: str) -> int:
    return start_from(mod, Either.import_module, 'module')


def start_path(path: str) -> int:
    try:
        setup_log()
        amino_log.debug(f'start_path: {path}')
        return Either.import_path(path).cata(L(import_error)(_, path), run_loop_uv)
    except Exception as e:
        return exception(e, path)


def start_file(path: str) -> int:
    p = Path(path)
    file = p / '__init__.py' if p.is_dir() else p
    return start_from(str(file), Either.import_file, 'file')


def start_json_config(data: str) -> int:
    @do(Either[str, int])
    def decode_and_run() -> Do:
        config = yield decode_json(data)
        return run_loop_uv(config)
    try:
        setup_log()
        amino_log.debug('starting plugin from json')
        return decode_and_run().value_or(error)
    except Exception as e:
        error(e)
        try:
            error(format_exception(e))
        except Exception as e:
            error(e)


__all__ = ('start_module', 'start_file', 'start_json_config', 'start_path',)
