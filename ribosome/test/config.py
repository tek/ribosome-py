from typing import Any

from ribosome.dispatch.component import Component

from amino import List, Map
from ribosome.request.handler.handler import RequestHandler
from ribosome.config.config import Config
from ribosome.trans.handler import FreeTrans


default_config_name = 'spec'


def single_trans_config(trans: FreeTrans, **kw: Any) -> Config:
    component = Component.cons(
        'main',
        request_handlers=List(
            RequestHandler.trans_cmd(trans)(**kw),
        )
    )
    return Config.cons(
        name=default_config_name,
        prefix=default_config_name,
        components=Map(main=component),
    )


__all__ = ('single_trans_config',)
