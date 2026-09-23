# Desktop application services

`clipboard.read_text()` returns owned UTF-8; `clipboard.write_text(text)` publishes
text on the UI thread. macOS uses NSPasteboard and Windows uses CF_UNICODETEXT.
Clipboard contention is recoverable. Text is bounded to 1 MiB; writes reject NUL
and malformed UTF-8. Linux clipboard support awaits the Linux window backend.

The file module now also exposes counted-text APIs directly usable from Luce:
`read_text`, `write_text`, `absolute_path`, `path_kind`, `ensure_directory`, and
`Entries(path)` with `count`, `name`, and `close`. File contents and entry names
returned by these APIs own their storage. Atomic text replacement preserves
existing permission bits and resolves existing symlinks to their targets.
Applications are responsible for detecting external changes before replacing
files. `read_text` defaults to a 4 MiB limit; names must be valid UTF-8.

`process.Command(program, arguments, directory = "", output_limit = 1048576,
environment = none)` starts a background worker without a shell. `is_finished`,
`revision`, `output`, `exit_code`, and `error_message` are nonblocking observations.
`output` copies a stable snapshot under a mutex and replaces malformed bytes for
display. Stdout/stderr are merged in observation order, not a guaranteed total
ordering of child writes. `cancel` requests termination; `close` cancels and joins.
Base owners must call close; Luce owns commands through ARC.

POSIX commands use nonblocking pipes and a dedicated process group. Cancellation
signals the group before reaping the leader; polling remains cancellable even
when a child has closed both output streams. On Windows, suspended creation and
job assignment precede execution. Separate read handles prevent output polling
from changing a child's file position. Captures use delete-on-close files. The
command's memory output is bounded; a producer can temporarily grow a Windows
capture file between polling intervals. Commands are intended for finite jobs;
interactive terminal input and PTY/ConPTY sessions are separate future APIs.

The ownership runtime now exits through `core`, removing its dependency on the
higher-level process module. Files and process can therefore expose owned APIs
without introducing a standard-library import cycle.

Native contracts: [NSPasteboard](https://developer.apple.com/documentation/appkit/nspasteboard),
[Windows clipboard](https://learn.microsoft.com/en-us/windows/win32/dataxchg/using-the-clipboard),
[POSIX process groups](https://pubs.opengroup.org/onlinepubs/009604599/functions/setpgid.html),
[Windows job objects](https://learn.microsoft.com/en-us/windows/win32/procthread/job-objects).
