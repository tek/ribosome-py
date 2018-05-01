

@lazy
def nvim_socket(self) -> str:
    return str(temp_dir('nvim_sockets') / List.random_string())

@property
def project_path(self) -> str:
    return str(base_dir().parent)

def connect_tmux(self, external: bool) -> Any:
    try:
        from chiasma.test.tmux_spec import tmux_spec_socket
        from chiasma.tmux import Tmux
    except ImportError:
        raise Exception('install chiasma to run nvim in a tmux pane')
    else:
        return Tmux.cons(socket=tmux_spec_socket if external else None)

@property
def tmux_window_external(self) -> Any:
    self.ribo_tmux = self.connect_tmux(True)
    from chiasma.io.compute import TmuxIO
    from chiasma.commands.window import windows
    @do(TmuxIO)
    def run() -> Do:
        ws = yield windows()
        yield TmuxIO.from_maybe(ws.head, 'tmux contains no windows')
    return run().unsafe(self.ribo_tmux)

@property
def tmux_window_local(self) -> Any:
    session = next(s for s in server.sessions if int(s['session_attached']) >= 1)
    return session.attached_window

@lazy
def tmux_window(self) -> Any:
    return self.tmux_window_external if self.tmux_nvim_external else self.tmux_window_local

def start_neovim_tmux_bg(self) -> None:
    conf = fixture_path('conf', 'tmux.conf')
    args = ['tmux', '-L', self.tmux_socket, '-f', str(conf)]
    master, slave = pty.openpty()
    self.subproc = subprocess.Popen(args, stdout=slave, stdin=slave, stderr=slave)
    env_args = self.vim_proc_env.map2(lambda k, v: f'{k}={v}').cons('env')
    cmd = env_args + self.nvim_cmdline
    from chiasma.commands.pane import send_keys
    send_keys(0, List(cmd.join_tokens)).unsafe(self.ribo_tmux)
    wait_for(Path(self.nvim_socket).is_socket)

def start_neovim_tmux_pane(self) -> None:
    self.ribo_tmux = self.connect_tmux(False)
    env_args = self.vim_proc_env.map2(lambda k, v: f'{k}={v}').cons('env')
    cmd = env_args + self.nvim_cmdline
    pid = os.getpid()
    from chiasma.io.compute import TmuxIO
    from chiasma.command import simple_tmux_cmd_attrs
    from psutil import Process
    @do(TmuxIO)
    def run() -> Do:
        ps = yield simple_tmux_cmd_attrs('list-panes', Nil, List('pane_pid', 'window_id'))
        def match(pane: Map[str, str]) -> bool:
            return Lists.wrap(Process(int(pane['pane_pid'])).children(recursive=True)).map(_.pid).contains(pid)
        current_pane = yield TmuxIO.from_maybe(ps.find(match), 'vim pane not found')
        window_id = current_pane['window_id']
        pane = yield simple_tmux_cmd_attrs('split-window', List('-t', window_id, '-d', '-P') + cmd, List('pane_id'))
        return pane[0]['pane_id'][1:]
    self.tmux_pane_id = run().unsafe(self.ribo_tmux)
    wait_for(Path(self.nvim_socket).is_socket)
    self.neovim = neovim.attach('socket', path=self.nvim_socket)
    self.neovim.command('python3 sys.path.insert(0, \'{}\')'.format(self.python_path))

def _cleanup_tmux(self) -> None:
    if self.tmux_pane_id is not None and not self.keep_tmux_pane:
        from chiasma.commands.pane import close_pane_id
        close_pane_id(self.tmux_pane_id).unsafe(self.ribo_tmux)

# def create_nvim_api(self, vim: Nvim) -> NvimApi:
#     return RiboNvimApi(self.plugin_name(), vim._session)

@abc.abstractmethod
def plugin_name(self) -> str:
    ...

def plugin_short_name(self) -> str:
    return self.plugin_name()

def full_cmd_prefix(self) -> str:
    return camelcase(self.plugin_name())

def short_cmd_prefix(self) -> str:
    return camelcase(self.plugin_short_name())

def teardown(self) -> None:
    IntegrationSpecBase.teardown(self)
    nvim_command('q!').unsafe(self.vim)
    if self._debug:
        self._log_out.foreach(self.log.info)
    if self.tmux_nvim:
        self._cleanup_tmux()
    if self.subproc is not None:
        self.subproc.kill()
    if self.tmux_nvim_external:
        from chiasma.io.compute import TmuxIO
        TmuxIO.write('kill-server').unsafe(self.ribo_tmux)


__all__ = ()
