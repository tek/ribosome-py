from amino.case import Case
from amino import Map
from amino.logging import module_log

from ribosome.nvim.syntax.expr import (SyntaxItem, SyntaxMatch, Highlight, HiLink, SyntaxKeyword, SyntaxRegion,
                                       SyntaxLiteral)

log = module_log()


def join_equals(data: Map[str, str]) -> str:
    return data.map2(lambda a, b: f'{a}={b}').join_tokens


class syntax_item_cmd(Case[SyntaxItem, str], alg=SyntaxItem):

    def keyword(self, data: SyntaxKeyword) -> str:
        options = data.options.join_tokens
        keywords = data.keywords.join_tokens
        params = join_equals(data.params)
        return f'syntax keyword {data.group} {data.keyword} {keywords} {options} {params}'

    def syntax_match(self, data: SyntaxMatch) -> str:
        options = data.options.join_tokens
        params = join_equals(data.params)
        return f'syntax match {data.group} /{data.pattern}/ {options} {params}'

    def region(self, data: SyntaxRegion) -> str:
        skip = data.skip.map(lambda a: f' skip=/{a}/').get_or_strict('')
        options = data.options.join_tokens
        params = join_equals(data.params)
        return f'syntax region {data.group} start=/{data.start}/{skip} end=/{data.end}/ {options} {params}'

    def literal(self, data: SyntaxLiteral) -> str:
        return data.cmd


def highlight_cmd(data: Highlight) -> str:
    values = join_equals(data.values)
    return f'highlight {data.group} {values}'


def hi_link_cmd(data: HiLink) -> str:
    return f'highlight link {data.group} {data.target}'


__all__ = ('syntax_item_cmd', 'highlight_cmd', 'hi_link_cmd',)
