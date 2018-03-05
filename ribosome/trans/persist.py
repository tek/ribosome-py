#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# __coconut_hash__ = 0x9e725a2f

# Compiled with Coconut version 1.3.0 [Dead Parrot]

# Coconut Header: -------------------------------------------------------------

from __future__ import generator_stop
import sys as _coconut_sys, os.path as _coconut_os_path
_coconut_file_path = _coconut_os_path.dirname(_coconut_os_path.abspath(__file__))
_coconut_sys.path.insert(0, _coconut_file_path)
from __coconut__ import _coconut, _coconut_NamedTuple, _coconut_MatchError, _coconut_igetitem, _coconut_base_compose, _coconut_forward_compose, _coconut_back_compose, _coconut_forward_star_compose, _coconut_back_star_compose, _coconut_pipe, _coconut_star_pipe, _coconut_back_pipe, _coconut_back_star_pipe, _coconut_bool_and, _coconut_bool_or, _coconut_none_coalesce, _coconut_minus, _coconut_map, _coconut_partial
from __coconut__ import *
_coconut_sys.path.remove(_coconut_file_path)

# Compiled Coconut: -----------------------------------------------------------

from typing import TypeVar  # line 1

from lenses import UnboundLens  # line 3

from amino import IO  # line 5
from amino import List  # line 5
from amino import Path  # line 5
from amino import Left  # line 5
from amino import do  # line 5
from amino import Do  # line 5
from amino.json import decode_json  # line 6
from amino.json import dump_json  # line 6

from ribosome.nvim import NvimIO  # line 8
from ribosome.nvim.io import NS  # line 9
from ribosome.config.config import Resources  # line 10
from ribosome.config.settings import Settings  # line 11

A = TypeVar('A')  # line 13
D = TypeVar('D')  # line 14
S = TypeVar('S', bound=Settings)  # line 15
CC = TypeVar('CC')  # line 16


settings: NS[Resources[S, D, CC], S] = NS.inspect(lambda a: a.settings)  # line 19


def mkdir(dir: 'Path') -> 'IO[None]':  # line 22
    return IO.delay(dir.mkdir, parents=True, exist_ok=True)  # line 23


@do(NvimIO[Path])  # line 26
def state_file(settings: 'S', name: 'str') -> 'Do':  # line 27
    dir = yield settings.project_state_dir.value_or_default  # line 28
    yield NvimIO.from_io(mkdir(dir))  # line 29
    yield NvimIO.pure(dir / f'{name}.json')  # line 30


@do(NvimIO[A])  # line 33
def load_json_data_from(name: 'str', file: 'Path') -> 'Do':  # line 34
    exists = yield NvimIO.from_io(IO.delay(file.exists))  # line 35
    if exists:  # line 36
        json = yield NvimIO.from_io(IO.delay(file.read_text))  # line 37
        yield NvimIO.pure(decode_json(json))  # line 38
    else:  # line 39
        yield NvimIO.pure(Left(f'state file {file} does not exist'))  # line 40


@do(NvimIO[A])  # line 43
def load_json_data(settings: 'S', name: 'str') -> 'Do':  # line 44
    file = yield state_file(settings, name)  # line 45
    yield load_json_data_from(file)  # line 46


@do(NS[Resources[S, D, CC], None])  # line 49
def load_json_state(name: 'str', store: 'UnboundLens') -> 'Do':  # line 50
    s = yield settings  # line 51
    state = yield NS.lift(load_json_data(s, name))  # line 52
    yield state.cata(lambda a: NS.pure(None), lambda d: NS.modify(store.set(d)))  # line 53


@do(NvimIO[None])  # line 56
def store_json_data(settings: 'S', name: 'str', data: 'A') -> 'Do':  # line 57
    file = yield state_file(settings, name)  # line 58
    json = yield NvimIO.from_either(dump_json(data))  # line 59
    yield NvimIO.from_io(IO.delay(file.write_text, json))  # line 60
    yield NvimIO.pure(None)  # line 61


@do(NS[Resources[S, D, CC], None])  # line 64
def store_json_state(name: 'str', fetch: '_coconut.typing.Callable[[D], A]') -> 'Do':  # line 65
    payload = yield NS.inspect(lambda s: fetch(s.data))  # line 66
    s = yield settings  # line 67
    yield NS.lift(store_json_data(s, name, payload))  # line 68

__all__ = ('load_json_state', 'store_json_data', 'store_json_state')  # line 70
