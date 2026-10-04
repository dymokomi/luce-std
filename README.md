# luce-std

Luce's standard library, as a package of its own. The compiler ships only the language
runtime (memory, ownership, interop, threads, strings, I/O streams); everything else a
program imports comes from here, versioned apart from the toolchain. It is written in Luce
Base and serves Luce and Base programs alike.

## Modules

| import | what it holds |
| --- | --- |
| `from luce_std import files` | Files and directories: whole-file text and bytes, `File` objects, listings, walks, metadata, copying, renaming, temporary directories |
| `from luce_std import paths` | Lexical filesystem paths: join, normalize, split |
| `from luce_std import process` | Running programs (`run`, background `Command`), environment variables, the working directory |
| `from luce_std import net` | TCP connections and listeners by host name, name lookup, UDP; HTTP and WebSocket wire formats for Base |
| `from luce_std import clock` | The monotonic clock, durations, sleeping, calendar dates and ISO 8601 |
| `from luce_std import random` | A seeded pseudo-random generator |
| `from luce_std import math` | The mathematical functions |
| `from luce_std import math32` | Single-precision mathematical functions |
| `from luce_std import unicode` | Unicode 17.0.0 casing and normalization |
| `from luce_std import utf8` | Strict UTF-8 scalar encoding and decoding |
| `from luce_std import crash` | Crash reports |

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

## Depends on

- luce-base compiler (the runtime modules)

## Platforms

macOS, Windows, Linux.

Native libraries it links, by platform (declared in `package.prisma`, linked only when the
program reaches code that needs them):

- windows: ws2_32

## Tests

`./test.sh` runs every module's `test` blocks and the unit tests through the native and C
backends, then the program checks under `tests/programs`. It expects the compiler beside
this checkout at `../luce-base/build/luce-base` (or `--base PATH`). When a Luce compiler is
at hand (`LUCE`, or `../luce/build/luce`), it also builds the Luce programs under
`tests/luce` against this checkout: each must print its expected output and leave no object
alive. `tests/luce/run.py --leaks` also runs them under macOS's `leaks`.

## License

MIT or Apache-2.0, at your option.
