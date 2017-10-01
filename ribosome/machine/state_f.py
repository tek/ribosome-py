#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# __coconut_hash__ = 0xabd12d3a

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

from lenses import Lens

from amino.do import tdo
from amino import IO
from amino import List
from amino import Path

from ribosome.nvim import NvimIO
from ribosome.nvim.io import NvimIOState
from ribosome.record import decode_json
from ribosome.record import encode_json
from ribosome.settings import AutoData

A = TypeVar('A')
D = TypeVar('D', bound=AutoData)


@tdo(NvimIOState[D, Path])
def history_file(name: 'str') -> 'Generator':
    settings = yield NvimIOState.inspect(lambda a: a.settings)
    dir = yield NvimIOState.lift(settings.state_dir.value_or_default)
    yield NvimIOState.lift(NvimIO.from_io(IO.delay(dir.mkdir, parents=True, exist_ok=True)))
    yield NvimIOState.pure(dir / f'{name}.json')


@tdo(NvimIOState[D, None])
def load_json_state(name: 'str', l: 'Lens') -> 'Generator':
    file = yield history_file(name)
    exists = yield NvimIOState.lift(NvimIO.from_io(IO.delay(file.exists)))
    if exists:
        json = yield NvimIOState.lift(NvimIO.from_io(IO.delay(file.read_text)))
        data = yield NvimIOState.lift(NvimIO.from_either(decode_json(json)))
        yield NvimIOState.modify(lambda a: l.bind(a).set(data))
    else:
        yield NvimIOState.pure(None)

@tdo(NvimIOState[D, None])
def store_json_state(name: 'str', data: '_coconut.typing.Callable[[D], A]') -> 'Generator':
    file = yield history_file(name)
    payload = yield NvimIOState.inspect(data)
    json = yield NvimIOState.lift(NvimIO.from_either(encode_json(payload)))
    yield NvimIOState.lift(NvimIO.from_io(IO.delay(file.write_text, json)))
    yield NvimIOState.pure(None)

__all__ = ('load_json_state', 'store_json_state')
