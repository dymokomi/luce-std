# HTTP and WebSocket primitives

The `net` standard module contains transport-independent HTTP/1.1 and WebSocket
codecs alongside its existing TCP/UDP sockets, readiness polling, deadlines and
cancellation. Import `net`; the public names are `HttpHead`, `HttpBodyDecoder`,
`HttpBodyWriter`, `WebSocketDecoder`, `WebSocketEncoder`, and the `http_*` and
`websocket_*` helpers. Source fragments are organized under `src/luce_std/net/http/`
and `src/luce_std/net/websocket/`; those directories share the `net` module namespace.

These are protocol primitives. Listeners, worker scheduling, request queues,
routing, static mounts and application lifecycle belong to the separate server
library. This stage does not implement or resume `luce-server`.

## HTTP

`http_head_end` finds the end of an accumulated head without consuming body or
pipelined bytes. When appending input, resume scanning at the previous length minus
at most three. Apply a byte limit while accumulating, including when no terminator
has arrived. `http_parse_request` and `http_parse_response` take exactly that head
and caller-owned `HttpField[]` storage. They preserve duplicate fields; `field`
returns the first and `fields` exposes all occurrences in order.

The parsed text borrows the input buffer and the field span borrows the field array.
Neither may be changed until the caller has finished using the head. Field values
are wire bytes, including obs-text, rather than a guarantee of UTF-8. Validate a
field's encoding before handing its raw value to a text-oriented application API.

HTTP/1.0 and HTTP/1.1 are supported. Parsing validates CRLF, field tokens and values,
Host authority syntax/cardinality, request-target forms and percent escapes,
Content-Length agreement and overflow, Connection token lists,
and transfer framing. The only implemented transfer coding is `chunked`; unsupported
codings and expectations have a distinct error category. No compression is decoded.
Content-Length together with Transfer-Encoding is rejected. The request method must
be provided when parsing a response so HEAD and successful CONNECT work correctly.
Informational responses are individual heads, followed by another response; a
successful CONNECT returns `tunnel` so the caller switches away from HTTP framing.

`HttpBodyDecoder` accepts arbitrary input fragments and returns consumed bytes,
a borrowed body span, an optional trailer, and completion. Stop at completion and
preserve the remaining input for the next message. Trailer fields borrow the
decoder's line buffer until the next call and are never merged into the original
headers. Framing/routing/content-processing trailers are rejected. Other trailers
remain subject to the application's field-specific policy.

Fixed-length, chunked and EOF-delimited bodies are supported. Call `finish` on
transport EOF: an unfinished fixed/chunked message fails. Errors latch, including
incomplete EOF; construct a new decoder for a new message. The decoder does not
accumulate the body and uses bounded internal line storage.

`http_encode_head` writes into caller storage, validates the completed head, and
returns its byte span. On error, do not transmit the partial output. Input text and
fields must not overlap output. Content-Length, Transfer-Encoding and Connection
are generated from `HttpHead`; callers cannot add competing fields. For HEAD,
encode the representation's metadata but do not write its body. For 304, empty
framing omits Content-Length; fixed framing can describe the selected representation.
The encoder emits empty reason phrases, which HTTP permits.

`HttpBodyWriter` borrows an `io.Writer`, handles short writes, enforces a fixed
length, or frames each nonempty write as a chunk. Call `finish` exactly once to
check completion and emit the final zero chunk. The writer does not flush or close
its destination. For EOF-delimited responses the caller must close the transport.
Any body-writer error makes that message unusable. The lower-level chunk helpers
are also available when the caller owns length/completion bookkeeping.

Default head limits are 32 KiB total, 8 KiB per line, and 100 fields; parsing also
respects the supplied field array's capacity. The default body limit is 1 GiB.
Chunk syntax is limited to an 8 KiB line, one million chunks, and trailers totaling
32 KiB and 100 fields. Head encoding uses the default head/field limits. Protocol
limits do not substitute for application deadlines or limits on concurrent peers.

For example, once a complete head has been accumulated, parsing borrows that
storage and uses a separate field array:

```lucb
import net

func inspect_request() -> !:
    let wire = "POST /items HTTP/1.1\r\nHost: example.test\r\nContent-Length: 5\r\n\r\n"
    var fields: net.HttpField[16]
    let head = try net.http_parse_request(wire.bytes, fields)
    assert(head.method == "POST" and head.target == "/items")
    var body = try net.HttpBodyDecoder.create(head.body_kind, head.body_length)
    let step = try body.consume("helloNEXT".bytes)
    assert(step.consumed == 5 and body.finished())
    assert((str)step.body == "hello")
    try body.finish()
```

Here `NEXT` remains unconsumed. A socket loop preserves that suffix, supplies more
input when needed, and calls `finish` when the transport reaches EOF.

## WebSocket

The opening handshake implements RFC 6455 version 13 over HTTP/1.1, without
extensions. `websocket_client_key` generates a fresh 16-byte OS-random nonce in
canonical base64. Save it and validate the reply with `websocket_check_response`.
The client/server handshake encoders use the same HTTP validation path.

`websocket_check_request` validates the upgrade's protocol requirements and returns
the borrowed key. The application must approve the request's Origin, identity and
service policy before sending the successful upgrade. Subprotocol selection is
explicit, case-sensitive, and restricted to a protocol the client offered. The
client rejects unsolicited subprotocols and all selected extensions. Offers must
contain unique tokens, with at most 128 subprotocols across all fields.

`websocket_accept_key` implements the RFC's fixed SHA-1/base64 transform. This is
only the public handshake calculation, not a general hashing or identity facility.
The SHA-1 compression code stays private to the WebSocket implementation.

`WebSocketDecoder.create(from_client)` fixes the direction: client frames must be
masked and server frames must be unmasked. `consume(input, output)` parses headers,
unmasks into a nonempty caller buffer and reports frame/message boundaries. Input,
output and decoder state must not overlap. Empty input is allowed. Keep consuming
the suffix indicated by `consumed`; do not equate a network read with a frame.

The decoder validates minimal length encodings, reserved bits/opcodes, cumulative
message limits, fragmentation and UTF-8 across text fragments. Ping/pong/close may
interrupt fragmented messages. Control frames must be final and at most 125 bytes;
close status/reason are checked at frame completion. Accumulate control payloads
until `frame_end` before acting on them. Data fragments are provisional until the
whole message validates; discard them if a later fragment fails.

A received close frame terminates that decoder's direction. `finish` requires a
complete close frame; bare TCP EOF is an abnormal closure. Replying to ping, echoing
close, enforcing close deadlines and closing the socket are connection policy for
the caller. The codec does not perform those network actions implicitly.

`WebSocketEncoder.create(client)` validates outgoing fragmentation, UTF-8 and
control frames, handles short writes, and uses a fresh random mask for every client
frame. Payload is streamed to the writer with a 4 KiB masking buffer. Both decoder
and encoder default to a 16 MiB frame limit and 16 MiB cumulative message limit;
constructors accept other limits. They keep no shared mutable state and require
serialized use per direction. Errors latch because prior data/output can already
have escaped; begin a new connection after failure.

## Verification

`tests/programs/net_protocols/check.sh` runs native optimization levels 0–3 and
supplemental C comparisons. It exercises fragmented input, pipeline boundaries,
fixed/chunked/EOF framing, duplicate lengths, malformed headers and trailers,
WebSocket masking/fragmentation/control/UTF-8, extended length boundaries, short
writes, deterministic malformed-input mutations, and handshake vectors computed
independently with Python's SHA-1/base64 implementation. Emitted client/server
frames are also decoded independently in Python at the 125/126 and 65535/65536
length boundaries. The suite is included in `test.sh`.

The governing references are [RFC 9112](https://www.rfc-editor.org/rfc/rfc9112.html),
[RFC 9110](https://www.rfc-editor.org/rfc/rfc9110.html), and
[RFC 6455](https://www.rfc-editor.org/rfc/rfc6455.html).

An optional downstream check uses an existing Luce compiler without making Base's
bootstrap depend on Luce:

```sh
python3 tests/programs/net_protocols/interop.py --luce ../luce/build/luce
```

It checks the handshake and frame codecs through a Base wrapper, copied string
lifetimes, first-class Base function calls, propagated failures and clean ARC
shutdown at all four native optimization levels. Its sources are test fixtures;
this does not build the future `luce-http-server` application.

Validated on 2026-09-10:

- Implementation `4b6294c` passed the full hosted gate on x86-64 Linux and ARM64
  macOS: [run 34524979514](https://github.com/dymokomi/luce-base/actions/runs/34524979514).
  Both logs include the protocol suite at native optimization levels 0–3 and both
  supplemental C comparison modes.
- The native bootstrap and assembly fixpoint passed locally, and the workspace
  `build/luce-base` was rebuilt with these primitives.
- The optional Luce/Base fixture at `543d938` passed all four native optimization
  levels on ARM64 macOS with Luce 0.1.6, including clean ARC shutdown.
- The HTTP example above compiled and ran with the native compiler.
