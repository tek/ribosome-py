from ribosome.machine.helpers import TransitionHelpers


class Component(TransitionHelpers):

    def __init__(self, name: str) -> None:
        self.name = name

    # @handle(UpdateRecord)
    # def message_update_record(self):
    #     return (
    #         self.record_lens(self.msg.tpe, self.msg.name) /
    #         __.modify(__.update_from_opt(self.msg.options)) /
    #         self.with_sub
    #     )

    # def record_lens(self, tpe, name) -> Maybe[Lens]:
    #     return Nothing

    # @trans.msg.unit(UpdateState, trans.st)
    # @do(State[Data, None])
    # def message_update_state(self) -> Generator:
    #     mod = __.update_from_opt(self.msg.options)
    #     l = yield self.state_lens(self.msg.tpe, self.msg.name)
    #     yield State.modify(lambda s: l.map(__.modify(mod)) | s)

    # def state_lens(self, tpe: str, name: str) -> State[Data, Maybe[Lens]]:
    #     return State.pure(Nothing)


__all__ = ('Component',)
