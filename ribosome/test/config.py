from typing import Any, Callable, Optional

from ribosome.config.component import Component

from amino import Map, Lists, Dat, Path, List, Nil
from amino.test import temp_dir
from ribosome.config.config import Config
from ribosome.compute.program import Program
from ribosome.rpc.api import RpcProgram, rpc
from ribosome.nvim.io.compute import NvimIO
from ribosome.compute.interpret import ProgIOInterpreter
from ribosome.nvim.io.api import N


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
    ) -> None:
        self.config = config
        self.pre = pre
        self.log_dir = log_dir
        self.log_file = log_file
        self.components = components
        self.io_interpreter = io_interpreter
        self.logger = logger


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


def single_trans_config(trans: Program, **kw: Any) -> Config:
    return spec_config(rpc.write(trans).conf(**kw))


__all__ = ('single_trans_config', 'spec_config')
