#!/usr/bin/env python3
"""Generate compact Unicode 17 tables from vendored, checksum-verified UCD data.

ASCII hexadecimal storage keeps the compiler's bootstrap syntax tree small: one
string per table instead of a syntax node for every integer. Each word has exactly
eight characters. Lookup code decodes individual words without allocating.
"""
import argparse
from functools import lru_cache
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data/unicode/17.0.0"
OUTPUT = ROOT / "src/luce_std/unicode/tables.lucb"


def records(name):
    for line in (DATA / name).read_text().splitlines():
        body = line.split("#", 1)[0].strip()
        if body:
            yield [field.strip() for field in body.split(";")]


def bounds(field):
    values = field.split("..")
    return int(values[0], 16), int(values[-1], 16)


def property_ranges(name, property_name, value=1):
    return [(first, last, value) for fields in records(name) if fields[1] == property_name
            for first, last in [bounds(fields[0])]]


def merged_ranges(ranges):
    result = []
    for first, last, value in sorted(ranges):
        assert 0 <= first <= last <= 0x10FFFF
        if result:
            assert result[-1][1] < first, "overlapping property ranges"
            if result[-1][1] + 1 == first and result[-1][2] == value:
                result[-1] = (result[-1][0], last, value)
                continue
        result.append((first, last, value))
    return result


def generate():
    manifest = json.loads((DATA / "manifest.json").read_text())
    for name, metadata in manifest.items():
        assert hashlib.sha256((DATA / name).read_bytes()).hexdigest() == metadata["sha256"], name
    decompositions, combining, upper, lower = {}, {}, {}, {}
    for fields in records("UnicodeData.txt"):
        scalar = int(fields[0], 16)
        if int(fields[3]):
            combining[scalar] = int(fields[3])
        mapping = fields[5].split()
        if mapping:
            compatibility = mapping[0].startswith("<")
            decompositions[scalar] = (compatibility, tuple(int(value, 16) for value in mapping[int(compatibility):]))
        for target, column in ((upper, 12), (lower, 13)):
            if fields[column]:
                target[scalar] = (int(fields[column], 16),)
    for fields in records("SpecialCasing.txt"):
        if fields[4]:
            # The only locale-independent conditional mapping is handled from
            # text context in Base. Locale-specific casing is deliberately separate.
            assert fields[4] == "Final_Sigma" or fields[4].split()[0] in {"tr", "az", "lt"}
            continue
        scalar = int(fields[0], 16)
        lower[scalar] = tuple(int(value, 16) for value in fields[1].split())
        upper[scalar] = tuple(int(value, 16) for value in fields[3].split())
    folding, turkic = {}, {}
    for fields in records("CaseFolding.txt"):
        scalar = int(fields[0], 16)
        mapping = tuple(int(value, 16) for value in fields[2].split())
        if fields[1] in {"C", "F"}:
            folding[scalar] = mapping
        elif fields[1] == "T":
            turkic[scalar] = mapping

    @lru_cache(None)
    def expand(scalar, compatibility):
        if 0xAC00 <= scalar <= 0xD7A3:
            index = scalar - 0xAC00
            return (0x1100 + index // 588, 0x1161 + (index % 588) // 28) + ((0x11A7 + index % 28,) if index % 28 else ())
        mapping = decompositions.get(scalar)
        if mapping is None or (mapping[0] and not compatibility):
            return (scalar,)
        return tuple(part for value in mapping[1] for part in expand(value, compatibility))

    canonical = {scalar: expand(scalar, False) for scalar in decompositions}
    compatible = {scalar: expand(scalar, True) for scalar in decompositions}
    excluded = set()
    for first, last, _ in property_ranges("DerivedNormalizationProps.txt", "Full_Composition_Exclusion"):
        excluded.update(range(first, last + 1))
    composition = []
    for scalar, (compatibility, mapping) in decompositions.items():
        if not compatibility and scalar not in excluded and len(mapping) == 2:
            assert combining.get(mapping[0], 0) == 0
            composition.append((*mapping, scalar))
    composition.sort()
    assert len({row[:2] for row in composition}) == len(composition)

    grapheme_names = "Other CR LF Control Extend ZWJ Regional_Indicator Prepend SpacingMark L V T LV LVT".split()
    graphemes = []
    for fields in records("auxiliary/GraphemeBreakProperty.txt"):
        first, last = bounds(fields[0])
        graphemes.append((first, last, grapheme_names.index(fields[1])))
    indic_names = {"Consonant": 1, "Linker": 2, "Extend": 3}
    indic = []
    for fields in records("DerivedCoreProperties.txt"):
        if fields[1] == "InCB":
            first, last = bounds(fields[0])
            indic.append((first, last, indic_names[fields[2]]))

    pool, pool_offsets = [], {}
    tables = []

    def emit(name, rows):
        rows = list(rows)
        words = [word for row in rows for word in row]
        assert all(0 <= word <= 0xFFFFFFFF for word in words)
        text = "".join(f"{word:08x}" for word in words)
        tables.extend([f"# {len(rows)} records; {len(rows[0]) if rows else 0} words per record.",
                       f'let {name}: str = "{text}"', ""])

    for name, mapping in (("canonical_mappings", canonical), ("compatibility_mappings", compatible),
                          ("upper_mappings", upper), ("lower_mappings", lower),
                          ("fold_mappings", folding), ("turkic_mappings", turkic)):
        rows = []
        for scalar, sequence in sorted(mapping.items()):
            if sequence == (scalar,):
                continue
            assert 1 <= len(sequence) <= 18
            if sequence not in pool_offsets:
                pool_offsets[sequence] = len(pool)
                pool.extend(sequence)
            rows.append((scalar, pool_offsets[sequence], len(sequence)))
        emit(name, rows)
    emit("mapping_scalars", [(scalar,) for scalar in pool])
    emit("composition_mappings", composition)
    emit("combining_ranges", merged_ranges((scalar, scalar, value) for scalar, value in combining.items()))
    emit("cased_ranges", merged_ranges(property_ranges("DerivedCoreProperties.txt", "Cased")))
    emit("case_ignorable_ranges", merged_ranges(property_ranges("DerivedCoreProperties.txt", "Case_Ignorable")))
    emit("whitespace_ranges", merged_ranges(property_ranges("PropList.txt", "White_Space")))
    emit("grapheme_ranges", merged_ranges(graphemes))
    emit("pictographic_ranges", merged_ranges(property_ranges("emoji/emoji-data.txt", "Extended_Pictographic")))
    emit("indic_ranges", merged_ranges(indic))
    header = (
        "#==============================================================================================\n"
        "#\n"
        "#   tables - Generated Unicode 17.0.0 property tables\n"
        "#\n"
        "#   DESCRIPTION:\n"
        "#       Generated by tools/unicode_tables.py; edit the generator, not these tables.\n"
        "#       Unicode 17.0.0 data: Copyright Unicode, Inc. Licensed under Unicode-3.0. The\n"
        "#       full permission notice is in data/unicode/17.0.0/LICENSE.txt.\n"
        "#\n"
        "#==============================================================================================\n\n"
    )
    return header + "\n".join(tables)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    generated = generate()
    if args.check:
        if not OUTPUT.exists() or OUTPUT.read_text() != generated:
            raise SystemExit("Unicode tables differ; run python3 tools/unicode_tables.py")
    else:
        OUTPUT.parent.mkdir(parents=True, exist_ok=True)
        OUTPUT.write_text(generated)
        print(f"wrote {OUTPUT.relative_to(ROOT)} ({len(generated)} bytes)")


if __name__ == "__main__":
    main()
