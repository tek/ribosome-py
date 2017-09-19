import sys
import logging


def remove_path(p: str) -> None:
    if p in sys.path:
        sys.path.remove(p)


def stage1(log: logging.Logger) -> int:
    try:
        remove_path('')
        remove_path('.')
        from amino import Lists
        from ribosome.host import start_file
        log.debug(f'ribosome_start_plugin: {sys.argv}, {sys.path}')
        def no_args() -> int:
            log.error(f'ribosome_start_plugin: missing argument for plugin file')
            return 1
        return Lists.wrap(sys.argv).lift(1).cata(start_file, no_args)
    except Exception as e:
        log.caught_exception_error(f'starting plugin with {sys.argv}', e)
        return 1


def start_plugin() -> int:
    from amino import with_log
    return with_log(stage1)


__all__ = ('start_plugin',)
