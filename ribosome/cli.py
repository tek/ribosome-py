import sys


def start_plugin() -> int:
    def no_args() -> int:
        from amino import amino_log
        amino_log.stderr(f'ribosome_start_plugin: missing argument for plugin file')
        return 1
    sys.path.remove('')
    sys.path.remove('.')
    from amino import Lists
    from ribosome.host import start_file
    return Lists.wrap(sys.argv).lift(1).cata(start_file, no_args)


__all__ = ('start_plugin',)
