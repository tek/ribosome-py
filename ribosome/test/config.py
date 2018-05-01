from typing import Any

from ribosome.config.component import Component

from amino import Map, Lists
from ribosome.request.handler.handler import RpcProgram, rpc, RpcOptions
from ribosome.config.config import Config
from ribosome.compute.program import Program


default_config_name = 'spec'


def spec_config(*rpc: RpcProgram) -> Config:
    component = Component.cons(
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
    return spec_config(rpc.write(trans).conf(RpcOptions.cons(**kw)))


__all__ = ('single_trans_config', 'spec_config')
