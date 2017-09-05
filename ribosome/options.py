from amino.options import EnvOption

development = EnvOption('RIBOSOME_DEVELOPMENT')
spec = EnvOption('RIBOSOME_SPEC')
file_log_level = EnvOption('RIBOSOME_FILE_LOG_LEVEL')
file_log_fmt = EnvOption('RIBOSOME_FILE_LOG_FMT')
nvim_log_file = EnvOption('NVIM_PYTHON_LOG_FILE')
ribo_log_file = EnvOption('RIBOSOME_LOG_FILE')

__all__ = ('development', 'spec', 'file_log_level', 'file_log_fmt', 'nvim_log_file', 'ribo_log_file')
