# Unicode text operations

The `unicode` module uses pinned Unicode **17.0.0** data. It accepts strict UTF-8,
including embedded NUL, noncharacters and unassigned scalar values. Malformed
input fails with `utf8.invalid_sequence`; it is never silently replaced. Inputs
are borrowed and must remain unchanged throughout an operation.

`to_upper` and `to_lower` implement full default casing, including expansions
and the contextual final Greek sigma rule. Language-specific Turkish, Azeri and
Lithuanian tailoring is not applied. `case_fold` implements full default case
folding; its `turkic` option selects the Unicode CaseFolding.txt T mappings.
Folding and lowercasing are different operations. None of these operations
normalizes the result or applies a locale's collation rules.

Results are fresh owned, NUL-terminated text, including unchanged or empty output.
Release them with `unicode.release` under the allocator that created them. An
optional `max_bytes` bounds result bytes and reports `strings.output_too_large`.
Preflight measures the result before allocation, and size overflow reports
`memory.exhausted`. No caller input is modified. Invalid input or a byte limit
may be reported as soon as encountered; error precedence is not a separate promise.

`is_whitespace` queries the Unicode White_Space property. `combining_class`
returns the canonical combining class. Invalid or unassigned scalar numbers
return false/zero for these queries. Existing `strings` byte and ASCII helpers
retain their original semantics.

The implementation and generated tables live in separate fragments under
`src/luce_std/unicode`. The generator checks hashes of the vendored upstream data;
normal builds and tests require no network access. Mapping tests use the pinned
UnicodeData, SpecialCasing and CaseFolding records, with independent Python
context tests for established characters. They cover expansion, NUL, unassigned
values, contextual sigma, exact output limits and allocation failure in all six
compiler configurations.

`normalize` supports NFC, NFD, NFKC and NFKD through `NormalizationForm`, defaulting
to NFC. Canonical forms preserve canonical equivalence; compatibility forms can
erase presentation distinctions. Normalization does not fold case or remove a
BOM. It uses fully expanded pinned mappings and algorithmic Hangul decomposition,
stable canonical ordering, and blocked canonical composition. Sorting is iterative
O(n log n) for n decomposed scalars, with classes cached during comparisons.
Scratch storage is needed only for an out-of-order combining run. Temporary arrays
are freed on every return, and `max_bytes` applies to the final encoded result after
composition, rather than the intermediate decomposition.

Normalization tests cover every relation in the official NormalizationTest file,
deduplicating repeated identical cases. Independent Python tests add established
characters, randomized sequences and long out-of-order combining runs. Together
they exercise 408,720 relations represented by 158,004 distinct cases, in all six
configurations. Allocation failures cover scalar, sorting and output buffers.

`GraphemeIterator.over` validates a complete UTF-8 view and returns an iterator
over default extended grapheme clusters. Construction and iteration allocate
nothing. Each nonempty result borrows the original bytes; `byte_offset` reports
the next boundary. EOF is stable, including for a zero iterator. Keep input bytes
alive and unchanged for the lifetime of the iterator and its returned views.
Clusters are logical text units, not terminal widths or rendered glyph counts.
State tracks Indic linker context, emoji ZWJ context and regional-indicator parity
without rescanning earlier text. Tests run all official GraphemeBreakTest cases
and long context sequences under a refusing allocator: 784 cases in all six
configurations. Word/sentence segmentation, collation and language-tailored casing
are outside this initial Unicode surface.

The normative references are [Unicode 17 chapter 3](https://www.unicode.org/versions/Unicode17.0.0/core-spec/chapter-3/)
the [normalization specification](https://www.unicode.org/reports/tr15/tr15-57.html),
the [segmentation specification](https://www.unicode.org/reports/tr29/tr29-47.html),
and the [pinned Unicode Character Database](https://www.unicode.org/Public/17.0.0/ucd/).
Source provenance and the upstream license are retained in `data/unicode/17.0.0`.
