#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# __coconut_hash__ = 0x8a1c51ae

# Compiled with Coconut version 1.3.0 [Dead Parrot]

# Coconut Header: -------------------------------------------------------------

from __future__ import generator_stop
import sys as _coconut_sys, os.path as _coconut_os_path
_coconut_file_path = _coconut_os_path.dirname(_coconut_os_path.abspath(__file__))
_coconut_sys.path.insert(0, _coconut_file_path)
from __coconut__ import _coconut, _coconut_NamedTuple, _coconut_MatchError, _coconut_tail_call, _coconut_tco, _coconut_igetitem, _coconut_base_compose, _coconut_forward_compose, _coconut_back_compose, _coconut_forward_star_compose, _coconut_back_star_compose, _coconut_pipe, _coconut_star_pipe, _coconut_back_pipe, _coconut_back_star_pipe, _coconut_bool_and, _coconut_bool_or, _coconut_none_coalesce, _coconut_minus, _coconut_map, _coconut_partial
from __coconut__ import *
_coconut_sys.path.remove(_coconut_file_path)

# Compiled Coconut: -----------------------------------------------------------

from typing import TypeVar

from lenses import UnboundLens

from amino import IO
from amino import List
from amino import Path
from amino import Left
from amino import do
from amino import Do
from amino.json import decode_json
from amino.json import dump_json

from ribosome.nvim import NvimIO
from ribosome.nvim.io import NS
from ribosome.config.config import Resources
from ribosome.config.settings import Settings

A = TypeVar('A')
D = TypeVar('D')
S = TypeVar('S', bound=Settings)
CC = TypeVar('CC')


settings: NS[Resources[S, D, CC], S] = NS.inspect(lambda a: a.settings)


@_coconut_tco
def mkdir(dir: 'Path') -> 'IO[None]':
    return _coconut_tail_call(IO.delay, dir.mkdir, parents=True, exist_ok=True)


@do(NvimIO[Path])
def state_file(settings: 'S', name: 'str') -> 'Do':
    dir = yield settings.project_state_dir.value_or_default
    yield NvimIO.from_io(mkdir(dir))
    yield NvimIO.pure(dir / f'{name}.json')


@do(NvimIO[A])
def load_json_data_from(name: 'str', file: 'Path') -> 'Do':
    exists = yield NvimIO.from_io(IO.delay(file.exists))
    if exists:
        json = yield NvimIO.from_io(IO.delay(file.read_text))
        yield NvimIO.pure(decode_json(json))
    else:
        yield NvimIO.pure(Left(f'state file {file} does not exist'))


@do(NvimIO[A])
def load_json_data(settings: 'S', name: 'str') -> 'Do':
    file = yield state_file(settings, name)
    yield load_json_data_from(file)


@do(NS[Resources[S, D, CC], None])
def load_json_state(name: 'str', store: 'UnboundLens') -> 'Do':
    s = yield settings
    state = yield NS.lift(load_json_data(s, name))
    yield state.cata(lambda a: NS.pure(None), lambda d: NS.modify(store.set(d)))


@do(NvimIO[None])
def store_json_data(settings: 'S', name: 'str', data: 'A') -> 'Do':
    file = yield state_file(settings, name)
    json = yield NvimIO.from_either(dump_json(data))
    yield NvimIO.from_io(IO.delay(file.write_text, json))
    yield NvimIO.pure(None)


@do(NS[Resources[S, D, CC], None])
def store_json_state(name: 'str', fetch: '_coconut.typing.Callable[[D], A]') -> 'Do':
    payload = yield NS.inspect(lambda s: fetch(s.data))
    s = yield settings
    yield NS.lift(store_json_data(s, name, payload))

__all__ = ('load_json_state', 'store_json_data', 'store_json_state')
