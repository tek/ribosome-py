from typing import Callable, Any

from amino.test.spec_spec import later, IntegrationSpec

from ribosome.test.integration.spec import VimIntegrationSpec, ExternalIntegrationSpec, PluginIntegrationSpec


class VimIntegrationSureHelpers:

    def _log_line(self, index, checker) -> None:
        def check() -> None:
            minlen = index if index >= 0 else abs(index + 1)
            len(self._log_out).should.be.greater_than(minlen)
            return checker(self._log_out[index]).should.be.ok
        later(check)

    def _log_contains(self, line) -> None:
        later(lambda: self._log_out.should.contain(line))

    def _buffer_content(self, data) -> None:
        later(lambda: self.content.should.equal(data))

    def _buffer_length(self, length) -> None:
        later(lambda: self.content.should.have.length_of(length))

    def _wait_for(self, assertion: Callable[..., bool], *a: Any, **kw: Any) -> None:
        later(assertion, *a, **kw)

    def _var_becomes(self, name, value) -> None:
        return self._wait_for(lambda: self.vim.vars(name).contains(value))

    def _pvar_becomes(self, name, value) -> None:
        return self._wait_for(lambda: self.vim.vars.p(name).contains(value))

    def _pvar_becomes_map(self, name, value, f) -> None:
        return self._wait_for(lambda: self.vim.vars.p(name).map(f).contains(value))


class VimIntegrationSpecSpec(VimIntegrationSpec, IntegrationSpec, VimIntegrationSureHelpers):

    def __init__(self) -> None:
        IntegrationSpec.__init__(self)
        VimIntegrationSpec.__init__(self)

    def setup(self) -> None:
        IntegrationSpec.setup(self)
        VimIntegrationSpec.setup(self)

    def teardown(self) -> None:
        IntegrationSpec.teardown(self)
        VimIntegrationSpec.teardown(self)


class ExternalIntegrationSpecSpec(ExternalIntegrationSpec, IntegrationSpec, VimIntegrationSureHelpers):

    def __init__(self) -> None:
        IntegrationSpec.__init__(self)
        ExternalIntegrationSpec.__init__(self)

    def setup(self) -> None:
        IntegrationSpec.setup(self)
        ExternalIntegrationSpec.setup(self)

    def teardown(self) -> None:
        IntegrationSpec.teardown(self)
        VimIntegrationSpec.teardown(self)


class PluginIntegrationSpecSpec(PluginIntegrationSpec, VimIntegrationSureHelpers):

    def __init__(self) -> None:
        IntegrationSpec.__init__(self)
        PluginIntegrationSpec.__init__(self)

    def setup(self) -> None:
        IntegrationSpec.setup(self)
        PluginIntegrationSpec.setup(self)

    def teardown(self) -> None:
        IntegrationSpec.teardown(self)
        VimIntegrationSpec.teardown(self)

__all__ = ('VimIntegrationSureHelpers', 'VimIntegrationSpecSpec', 'ExternalIntegrationSpecSpec',
           'PluginIntegrationSpecSpec')
