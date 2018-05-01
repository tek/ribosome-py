#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# __coconut_hash__ = 0xa55d45aa

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
from ribosome.nvim.io.api import N  # line 11

A = TypeVar('A')  # line 13
D = TypeVar('D')  # line 14
CC = TypeVar('CC')  # line 15


settings: NS[Resources[D, CC], S] = NS.inspect(lambda a: a.settings)  # line 18


def mkdir(dir: 'Path') -> 'IO[None]':  # line 21
    return IO.delay(dir.mkdir, parents=True, exist_ok=True)  # line 22


@do(NvimIO[Path])  # line 25
def state_file(settings: 'S', name: 'str') -> 'Do':  # line 26
    dir = yield settings.project_state_dir.value_or_default  # line 27
    yield N.from_io(mkdir(dir))  # line 28
    yield N.pure(dir / f'{name}.json')  # line 29


@do(NvimIO[A])  # line 32
def load_json_data_from(name: 'str', file: 'Path') -> 'Do':  # line 33
    exists = yield N.from_io(IO.delay(file.exists))  # line 34
    if exists:  # line 35
        json = yield N.from_io(IO.delay(file.read_text))  # line 36
        yield N.pure(decode_json(json))  # line 37
    else:  # line 38
        yield N.pure(Left(f'state file {file} does not exist'))  # line 39


@do(NvimIO[A])  # line 42
def load_json_data(settings: 'S', name: 'str') -> 'Do':  # line 43
    file = yield state_file(settings, name)  # line 44
    yield load_json_data_from(file)  # line 45


@do(NS[Resources[D, CC], None])  # line 48
def load_json_state(name: 'str', store: 'UnboundLens') -> 'Do':  # line 49
    s = yield settings  # line 50
    state = yield NS.lift(load_json_data(s, name))  # line 51
    yield state.cata(lambda a: NS.pure(None), lambda d: NS.modify(store.set(d)))  # line 52


@do(NvimIO[None])  # line 55
def store_json_data(settings: 'S', name: 'str', data: 'A') -> 'Do':  # line 56
    file = yield state_file(settings, name)  # line 57
    json = yield N.from_either(dump_json(data))  # line 58
    yield N.from_io(IO.delay(file.write_text, json))  # line 59
    yield N.pure(None)  # line 60


@do(NS[Resources[D, CC], None])  # line 63
def store_json_state(name: 'str', fetch: '_coconut.typing.Callable[[D], A]') -> 'Do':  # line 64
    payload = yield NS.inspect(lambda s: fetch(s.data))  # line 65
    s = yield settings  # line 66
    yield NS.lift(store_json_data(s, name, payload))  # line 67

__all__ = ('load_json_state', 'store_json_data', 'store_json_state')  # line 69
