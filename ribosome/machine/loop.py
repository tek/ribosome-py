#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# __coconut_hash__ = 0x61c7045f

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

from amino import Just
from amino import Nothing
from amino import Right
from amino import Left
from amino import L
from amino import _
from amino import __
from amino.state import EvalState
from amino.state import EvalState
from amino.do import tdo

from ribosome.machine.transition import TransitionResult
from ribosome.machine.transition import TransitionLog
from ribosome.machine.transition import TransitionResult
from ribosome.machine.process_messages import PrioQueue
from ribosome.logging import ribo_log
from ribosome.machine.base import TransState
from ribosome.request.dispatch import PluginState
from ribosome.request.dispatch import ComponentState
from ribosome.machine.message_base import Message

A = TypeVar('A')
D = TypeVar('D')


@_coconut_tco
def process_message(messages: 'PrioQueue[A]', state: 'D', send: '_coconut.typing.Callable[[D, A], TransState]') -> '(PrioQueue[A], TransState)':
    def process1(*_coconut_match_to_args, **_coconut_match_to_kwargs):
        _coconut_match_check = False
        if (_coconut.len(_coconut_match_to_args) == 1) and (_coconut.isinstance(_coconut_match_to_args[0], Right)) and (_coconut.len(_coconut_match_to_args[0]) == 1) and (_coconut.isinstance(_coconut_match_to_args[0][0], _coconut.abc.Sequence)) and (_coconut.len(_coconut_match_to_args[0][0]) == 2) and (_coconut.isinstance(_coconut_match_to_args[0][0][0], _coconut.abc.Sequence)) and (_coconut.len(_coconut_match_to_args[0][0][0]) == 2):
            prio = _coconut_match_to_args[0][0][0][0]
            msg = _coconut_match_to_args[0][0][0][1]
            rest = _coconut_match_to_args[0][0][1]
            if not _coconut_match_to_kwargs:
                _coconut_match_check = True
        if not _coconut_match_check:
            _coconut_match_err = _coconut_MatchError("pattern-matching failed for " "'def process1(Right(((prio, msg), rest))) = rest, send(state, msg)'" " in " + _coconut.repr(_coconut.repr(_coconut_match_to_args)))
            _coconut_match_err.pattern = 'def process1(Right(((prio, msg), rest))) = rest, send(state, msg)'
            _coconut_match_err.value = _coconut_match_to_args
            raise _coconut_match_err

        return rest, send(state, msg)
    @addpattern(process1)
    def process1(*_coconut_match_to_args, **_coconut_match_to_kwargs):
        _coconut_match_check = False
        if (_coconut.len(_coconut_match_to_args) == 1) and (_coconut.isinstance(_coconut_match_to_args[0], Left)) and (_coconut.len(_coconut_match_to_args[0]) == 1):
            err = _coconut_match_to_args[0][0]
            if not _coconut_match_to_kwargs:
                _coconut_match_check = True
        if not _coconut_match_check:
            _coconut_match_err = _coconut_MatchError("pattern-matching failed for " "'def process1(Left(err)) = messages, EvalState.pure(TransitionResult.empty(state))'" " in " + _coconut.repr(_coconut.repr(_coconut_match_to_args)))
            _coconut_match_err.pattern = 'def process1(Left(err)) = messages, EvalState.pure(TransitionResult.empty(state))'
            _coconut_match_err.value = _coconut_match_to_args
            raise _coconut_match_err

        return messages, EvalState.pure(TransitionResult.empty(state))
    return _coconut_tail_call(process1, messages.get)
