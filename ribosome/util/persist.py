#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# __coconut_hash__ = 0x6a61a38b

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

from ribosome.nvim.io.compute import NvimIO  # line 8
from ribosome.nvim.io.state import NS  # line 9
from ribosome.config.resources import Resources  # line 10
from ribosome.config.settings import Settings  # line 11
from ribosome.nvim.io.api import N  # line 12

A = TypeVar('A')  # line 14
D = TypeVar('D')  # line 15
S = TypeVar('S', bound=Settings)  # line 16
CC = TypeVar('CC')  # line 17


settings: NS[Resources[S, D, CC], S] = NS.inspect(lambda a: a.settings)  # line 20


def mkdir(dir: 'Path') -> 'IO[None]':  # line 23
    return IO.delay(dir.mkdir, parents=True, exist_ok=True)  # line 24


@do(NvimIO[Path])  # line 27
def state_file(settings: 'S', name: 'str') -> 'Do':  # line 28
    dir = yield settings.project_state_dir.value_or_default  # line 29
    yield N.from_io(mkdir(dir))  # line 30
    yield N.pure(dir / f'{name}.json')  # line 31


@do(NvimIO[A])  # line 34
def load_json_data_from(name: 'str', file: 'Path') -> 'Do':  # line 35
    exists = yield N.from_io(IO.delay(file.exists))  # line 36
    if exists:  # line 37
        json = yield N.from_io(IO.delay(file.read_text))  # line 38
        yield N.pure(decode_json(json))  # line 39
    else:  # line 40
        yield N.pure(Left(f'state file {file} does not exist'))  # line 41


@do(NvimIO[A])  # line 44
def load_json_data(settings: 'S', name: 'str') -> 'Do':  # line 45
    file = yield state_file(settings, name)  # line 46
    yield load_json_data_from(file)  # line 47


@do(NS[Resources[S, D, CC], None])  # line 50
def load_json_state(name: 'str', store: 'UnboundLens') -> 'Do':  # line 51
    s = yield settings  # line 52
    state = yield NS.lift(load_json_data(s, name))  # line 53
    yield state.cata(lambda a: NS.pure(None), lambda d: NS.modify(store.set(d)))  # line 54


@do(NvimIO[None])  # line 57
def store_json_data(settings: 'S', name: 'str', data: 'A') -> 'Do':  # line 58
    file = yield state_file(settings, name)  # line 59
    json = yield N.from_either(dump_json(data))  # line 60
    yield N.from_io(IO.delay(file.write_text, json))  # line 61
    yield N.pure(None)  # line 62


@do(NS[Resources[S, D, CC], None])  # line 65
def store_json_state(name: 'str', fetch: '_coconut.typing.Callable[[D], A]') -> 'Do':  # line 66
    payload = yield NS.inspect(lambda s: fetch(s.data))  # line 67
    s = yield settings  # line 68
    yield NS.lift(store_json_data(s, name, payload))  # line 69

__all__ = ('load_json_state', 'store_json_data', 'store_json_state')  # line 71
