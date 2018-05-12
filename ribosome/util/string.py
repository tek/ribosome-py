

def escape_squote(text: str) -> str:
    return text.replace("'", "''")


def escape_dquote(text: str) -> str:
    return text.replace('"', '\\"')


def escape_quote(text: str) -> str:
    return escape_dquote(escape_squote(text))


def quote_for_ex(text: str) -> str:
    return f'\'{escape_quote(text)}\''


__all__ = ('escape_squote', 'escape_dquote', 'escape_quote',)
