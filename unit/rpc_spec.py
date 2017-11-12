from kallikrein import k, Expectation

from ribosome import function

from amino.boolean import true


class RpcSpecPlugin:

    @function(sync=True)
    def h1(self, a: int) -> None:
        pass


plug = RpcSpecPlugin()


class RpcSpec:
    '''
    test $test
    '''

    def test(self) -> Expectation:
        return k(plug.h1.spec.sync) == true

__all__ = ('RpcSpec',)
