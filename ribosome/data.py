
class LegacyData:
    # vim_facade = maybe_field((NvimFacade, AsyncVimProxy))
    # sub_states = field(Map, initial=Map())
    # debug = bool_field()

    # def sub_state_m(self, name):
    #     return self.sub_states.get(name)

    # def sub_state(self, name, default: Callable[[], Any]):
    #     return self.sub_state_m(name) | default

    # def with_sub_state(self, name, state):
    #     new_states = self.sub_states + (name, state)
    #     return self.set(sub_states=new_states)

__all__ = ('LegacyData',)
