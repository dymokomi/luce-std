# luce-std

Luce's standard library, as a package of its own. The compiler ships only the language runtime (memory, ownership, interop, threads, strings, I/O streams); everything else a program imports comes from here, versioned apart from the toolchain.

## Modules

| import | what it holds |
| --- | --- |
| `import utf8` | Strict UTF-8 scalar encoding and decoding |
| `import unicode` | Unicode 17.0.0 text operations |
| `import paths` | Lexical filesystem paths |
| `import math` | The mathematical functions of the standard library |
| `import math32` | Single-precision mathematical functions |
| `import net` | TCP/UDP sockets, HTTP and WebSocket |
| `import files` | Files, directories and their operations |
| `import crash` | Crash reports |
| `import process` | Running a child process to completion |

## Using it

Add the dependency to `package.prisma`; the modules keep their short names:

```prisma
def dependency "luce-std" {
    str owner = "dymokomi"
    str version = "^0.1.0"
}
```

## Depends on

- luce-base compiler (the runtime modules)

## Platforms

macOS, Windows, Linux.

Native libraries it links, by platform (declared in `package.prisma`, linked only when the program reaches code that needs them):

- windows: ws2_32

## Tests

`./test.sh` runs every module's `test` blocks and the unit tests through the native and C backends, then the program checks under `tests/programs`. It expects the compiler beside this checkout at `../luce-base/build/luce-base` (or `--base PATH`).

## License

MIT or Apache-2.0, at your option.
