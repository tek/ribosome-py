from kallikrein import Expectation
from kallikrein.expectable import kio
from kallikrein.matchers.lines import have_lines

from amino.test.spec import SpecBase
from amino import List, Nil

from ribosome.config.settings import ribosome_session_name
from ribosome.util.doc.data import StaticDoc
from ribosome.util.doc.markdown import markdown_compiler, MarkdownCompilerConfig
from ribosome.util.doc.generate import generate_doc
from ribosome.util.doc.format import CompilerConfig


target = '''# Components

# Settings

## `g:ribosome_session_name`

project name from user var

A custom session name for the state dir can be specified.

'''
conf = MarkdownCompilerConfig.cons(CompilerConfig.cons('ribosome'))


class DocSpec(SpecBase):
    '''
    markdown compiler $markdown
    '''

    def markdown(self) -> Expectation:
        return kio(generate_doc, Nil, List(ribosome_session_name), StaticDoc.cons(), markdown_compiler(conf)).must(
            have_lines(target))


__all__ = ('DocSpec',)
