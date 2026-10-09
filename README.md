# luce-std

Luce's standard library, as a package of its own. The compiler ships only the language
runtime (memory, ownership, interop, threads, strings, I/O streams); everything else a
program imports comes from here, versioned apart from the toolchain. It is written in Luce
Base and serves Luce and Base programs alike.

## Modules

| import | what it holds |
| --- | --- |
| `from luce_std import files` | Files and directories: whole-file text and bytes, `File` objects, listings, walks, metadata, copying, renaming, temporary directories, read-only memory-mapped files (`map`) |
| `from luce_std import paths` | Lexical filesystem paths: join, normalize, split |
| `from luce_std import process` | Running programs (`run`, background `Command`), environment variables, the working directory |
| `from luce_std import net` | TCP connections and listeners by host name, name lookup, UDP; HTTP and WebSocket wire formats for Base; for event loops, connects that do not wait (`Connection.start_connect`, `finish_connect`) and name lookups on a thread of their own (`Lookup`) |
| `from luce_std import clock` | The monotonic clock, durations, sleeping, calendar dates and ISO 8601 |
| `from luce_std import random` | A seeded pseudo-random generator |
| `from luce_std import math` | The mathematical functions |
| `from luce_std import math32` | Single-precision mathematical functions |
| `from luce_std import sort` | Sorting Base arrays in place without allocating: `sort(values)`, `by(values, less)`, `using(values, context, less)` (introsort, O(n log n), not stable); `stable` and `stable_using` keep equal values in order; `order` and `order_by` write the indices that would sort an array (argsort). Luce lists have `sort` and `sorted` of their own |
| `from luce_std import parallel` | A parallel `for` over independent items for Base: `for_each(count, context, work)` runs `work(context, index, worker)` on one thread per processor, `for_each_range` hands out chunks of indices |
| `from luce_std import unicode` | Unicode 17.0.0 casing and normalization |
| `from luce_std import utf8` | Strict UTF-8 scalar encoding and decoding |
| `from luce_std import collections` | Growable storage for Base: `List[T]`, a byte `Buffer`, and a `TextPool` of copies that never move |
| `from luce_std import crash` | Crash reports in `~/.luce/crashes`, named after the program's package; hooks that save work after a trap (`on_crash`, `recovery_directory`, `note_recovery`); starting the program again to show its report (`relaunch_on_crash`, `report_to_show`), which luce-ui's crash window uses. Nothing is sent anywhere |

## Using it

Add the dependency with `luc add dymokomi/luce-std`, or in `package.prisma`:

```prisma
def dependency "luce-std" {
    str owner = "dymokomi"
    str version = "^0.4.0"
}
```

From Luce, the modules read like Python's:

```luce
from luce_std import files, clock

pub func main(arguments: list[str]) -> int!:
    let start = clock.now()
    with files.open("notes.txt") as notes:
        while let line = notes.read_line():
            print(line)
    print(f"read in {start.elapsed().seconds()} s at {clock.DateTime.now().text()}")
    return 0
```

[The standard library](https://luce.luciaos.com/guide/standard-library/) chapter of
the Luce guide describes what Luce programs call. A Luce program sees the functions,
structs and objects whose signatures cross the Base boundary; the rest is for Base.

## From Base

Functions that answer fresh storage, such as `files.read`, `files.list`, `paths.join`,
`process.run` or `unicode.to_upper`, answer an `interop.Owned[...]` result. Luce copies the
value and releases it. A Base caller reads `.value` and releases the result when done:

```lucb
let names = try files.list("notes")
defer names.release()
for name in names.value:
    print(name)
```

The storage comes from the allocator current at the call; texts are NUL-terminated, so they
may be passed on as `c.str`. Objects Luce holds (`files.File`, `files.TemporaryDirectory`,
`net.Connection`, `net.Listener`, `process.Command`) remain ordinary values in Base.

### Mapped files

`files.map(path)` answers a whole file's bytes as a read-only mapping, much as Python's
`mmap.mmap(f.fileno(), 0, access=mmap.ACCESS_READ)` does, but without a file to keep open:
the result is an `interop.Owned[const u8[]]` whose `release()` unmaps it.

```lucb
let font = try files.map("/System/Library/Fonts/Helvetica.ttc")
defer font.release()
let tag = font.value[..<4]          # pages are read from the file as they are touched
```

The mapping is shared, so its pages belong to the file: they cost nothing until read, the
system may drop them under memory pressure and read them again, and every process mapping
the same file shares them. That suits large files read in parts, such as fonts. An empty
file answers an empty view. The view stays valid after the file is closed, renamed or opened
elsewhere, but not after it is truncated (reading past the new end faults, as it does in
Python); write a replacement through `write_atomic` instead of changing a mapped file in
place. A Luce program calling `files.map` receives a copy as `bytes`, so from Luce it reads
like `files.read`.

### Growable storage

`collections` is for Base only; Luce has its own `list` and `bytes`. A zero value of each
type is empty and ready. The first growth takes the current allocator and keeps it, as
`strings.Builder` does; `destroy` gives the storage back, after which the value may be used
again.

```lucb
from luce_std import collections

var rows: collections.List[Row]
defer rows.destroy()
try rows.append(Row(id = 1))
try rows.insert(0, Row(id = 0))
rows.remove(1)                      # keeps the order of the rest; remove(index, count) for a run
for row in rows.view(): ...         # const Row[]; rows.items() is a Row[] to change or sort

var line: collections.Buffer        # an io.Writer
defer line.destroy()
try line.put_text("total ")
try line.put_number(42)
try strings.write_f64(&line, 2.5, ".2f")
print(line.text())                  # the bytes as far as they are valid UTF-8
let path = try line.terminated()    # a c.str, valid until the next change

var pool: collections.TextPool      # copies stay where they are until pool.destroy()
let name = try pool.keep_text(column_bytes)
```

- `List[T]`: `length`, `capacity`, `reserve`, `append`, `insert`, `remove(index, count = 1)`,
  `truncate`, `at`, `set`, `view`, `items`, `clear`, `destroy`. The capacity at least
  doubles when it grows, so `view` and `items` are valid until the next `append`, `insert`
  or `reserve`. An index out of range traps, as indexing a span does.
- `Buffer`: `put`, `put_text`, `put_byte`, `put_number`, `write` (io.Writer), `remove`,
  `truncate`, `view`, `text`, `terminated`, `length`, `reserve`, `clear`, `destroy`.
- `TextPool`: `keep(bytes)`, `keep_text(bytes)` (cut where the bytes stop being valid UTF-8),
  `destroy`. Copies go into 64 KiB chunks; a larger one gets a chunk of its own.

## Depends on

- luce-base compiler (the runtime modules)

## Platforms

macOS, Windows, Linux.

Native libraries it links, by platform (declared in `package.prisma`, linked only when the
program reaches code that needs them):

- windows: ws2_32

## Tests

`luc test` runs every module's `test` blocks, with the module tests under `tests/<module>/`,
and every program under `tests/`: the file, network, process, math, Unicode and crash
checks, the HTTP server driven by curl, the Unicode tables against their generator, and the
Luce programs `tests/luce_*`, each of which must print its expected output and leave no
object alive.

The same run passes on macOS, Linux and Windows. The checks whose C reference is POSIX code,
with faults injected through `dlsym` or FIFOs made by `mkfifo`, skip themselves on Windows
and say why; `tests/windows_files` and `tests/windows_network` check Windows' side of the
file and network contracts instead, and skip elsewhere. On Windows, run it from Git's bash,
whose `sh`, `echo` and `nm` some checks call.

## License

MIT or Apache-2.0, at your option.
