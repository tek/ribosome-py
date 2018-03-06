from typing import Any

from ribosome.dispatch.component import Component

from amino import Map, Lists
from ribosome.request.handler.handler import RequestHandler
from ribosome.config.config import Config
from ribosome.trans.handler import FreeTrans


default_config_name = 'spec'


def spec_config(*request_handlers: RequestHandler) -> Config:
    component = Component.cons(
        'main',
        request_handlers=Lists.wrap(request_handlers)
    )
    return Config.cons(
        name=default_config_name,
        prefix=default_config_name,
        components=Map(main=component),
    )


def single_trans_config(trans: FreeTrans, **kw: Any) -> Config:
    return spec_config(RequestHandler.trans_cmd(trans)(**kw))


__all__ = ('single_trans_config', 'spec_config')
