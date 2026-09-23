# Pinned Unicode data

The `17.0.0` directory contains final upstream Unicode Character Database files
and official conformance vectors. `manifest.json` records each source URL and
SHA-256 digest. Keep this version fixed until an intentional Unicode upgrade.
The upstream license and copyright notice are in `17.0.0/LICENSE.txt`.

Run `python3 tools/unicode_tables.py` to regenerate Base lookup tables, or add
`--check` to verify both input digests and generated output. The normal gate
performs this check without downloading data or importing third-party Python
packages. Packed ASCII hexadecimal tables avoid creating one bootstrap syntax
node per numeric entry; lookup decodes individual immutable words without allocation.

These data and their derived tables retain the Unicode-3.0 license. Include the
upstream notice when distributing them, including alongside compiled artifacts
that incorporate the tables. The surrounding Base implementation retains the
repository's Apache-2.0/MIT licensing.
