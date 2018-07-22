from __future__ import annotations
from typing import Any, Callable, Optional

from ribosome.config.component import Component

from amino import Map, Lists, Dat, Path, List, Nil, Maybe
from amino.test import temp_dir
from ribosome.config.config import Config
from ribosome.compute.program import Program
from ribosome.rpc.api import RpcProgram, rpc
from ribosome.nvim.io.compute import NvimIO
from ribosome.compute.interpret import ProgIOInterpreter
from ribosome.nvim.io.api import N
from ribosome.test.request import Handler, no_handler


default_config_name = 'spec'
no_pre = lambda: N.unit


class TestConfig(Dat['TestConfig']):

    @staticmethod
    def cons(
            config: Config,
            pre: Callable[[], NvimIO[None]]=None,
            log_dir: Path=None,
            log_file: Path=None,
            components: List[str]=Nil,
            io_interpreter: ProgIOInterpreter=None,
            logger: Program[None]=None,
            vars: Map[str, Any]=Map(),
            request_handler: Handler=no_handler,
            function_handler: Handler=no_handler,
            command_handler: Handler=no_handler,
            autostart: bool=True,
            config_path: str=None,
    ) -> 'TestConfig':
        ld = log_dir or temp_dir('log')
        lf = log_file or ld / config.basic.name
        return TestConfig(
            config,
            pre or no_pre,
            ld,
            lf,
            components,
            io_interpreter,
            logger,
            vars,
            request_handler,
            function_handler,
            command_handler,
            autostart,
            Maybe.optional(config_path),
        )

    def __init__(
            self,
            config: Config,
            pre: Callable[[], NvimIO[None]],
            log_dir: Path,
            log_file: Path,
            components: List[str],
            io_interpreter: Optional[ProgIOInterpreter],
            logger: Optional[Program[None]],
            vars: Map[str, Any],
            request_handler: Handler,
            function_handler: Handler,
            command_handler: Handler,
            autostart: bool,
            config_path: Maybe[str],
    ) -> None:
        self.config = config
        self.pre = pre
        self.log_dir = log_dir
        self.log_file = log_file
        self.components = components
        self.io_interpreter = io_interpreter
        self.logger = logger
        self.vars = vars
        self.request_handler = request_handler
        self.function_handler = function_handler
        self.command_handler = command_handler
        self.autostart = autostart
        self.config_path = config_path

    def with_vars(self, **kw: Any) -> 'TestConfig':
        return self.copy(vars=self.vars ** Map(kw))


def spec_config(*rpc: RpcProgram) -> Config:
    component: Component = Component.cons(
        'main',
        rpc=Lists.wrap(rpc)
    )
    return Config.cons(
        name=default_config_name,
        prefix=default_config_name,
        components=Map(main=component),
        internal_component=False,
    )


def single_prog_config(prog: Program, **kw: Any) -> Config:
    return spec_config(rpc.write(prog).conf(**kw))


__all__ = ('single_prog_config', 'spec_config')
