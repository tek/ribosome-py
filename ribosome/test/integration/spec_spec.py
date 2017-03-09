from amino.test.spec_spec import later


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
