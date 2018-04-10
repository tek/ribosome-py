from typing import TypeVar, Any, Generic

from amino import List, Boolean
from amino.dat import Dat

from ribosome.data.plugin_state import Programs
from ribosome.data.plugin_state_holder import PluginStateHolder

D = TypeVar('D')


class RequestJob(Generic[D], Dat['RequestJob']):

    def __init__(
            self,
            state: PluginStateHolder[D],
            name: str,
            args: List[Any],
            sync: bool,
            bang: Boolean,
    ) -> None:
        self.state = state
        self.name = name
        self.args = args
        self.sync = sync
        self.bang = Boolean(bang)

    @property
    def plugin_name(self) -> str:
        return self.state.state.basic.name

    @property
    def sync_prefix(self) -> str:
        return '' if self.sync else 'a'

    @property
    def desc(self) -> str:
        return f'{self.sync_prefix}sync request {self.name}({self.args}) to `{self.plugin_name}`'

    @property
    def programs(self) -> Programs:
        return self.state.state.programs


__all__ = ('RequestJob',)
