#!/usr/bin/env python3
"""Add HTTP/1.1 option compatibility to a private Wine winhttp.dll copy."""

import argparse
import hashlib
import json
from pathlib import Path
import struct

import pefile

from patch_msvcrt import align, export


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("adapter", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError(args.output)

    source_bytes = args.source.read_bytes()
    helper_bytes = args.adapter.read_bytes()
    host = pefile.PE(data=source_bytes)
    helper = pefile.PE(data=helper_bytes)
    for pe in (host, helper):
        if pe.FILE_HEADER.Machine != 0x8664 or pe.OPTIONAL_HEADER.Magic != 0x20B:
            raise ValueError("Both inputs must be x86-64 PE32+ DLLs")
        if not pe.FILE_HEADER.Characteristics & 0x2000:
            raise ValueError("Input is not a DLL")
    if any(s.Name.rstrip(b"\0") == b".httpfix" for s in host.sections):
        raise ValueError("Source already contains the HTTP adapter")
    if host.OPTIONAL_HEADER.DATA_DIRECTORY[4].Size:
        raise ValueError("Refusing to patch an Authenticode-signed runtime")
    if getattr(helper, "DIRECTORY_ENTRY_IMPORT", []):
        raise ValueError("Adapter must have no DLL imports")
    for block in getattr(helper, "DIRECTORY_ENTRY_BASERELOC", []):
        if any(entry.type for entry in block.entries):
            raise ValueError("Adapter contains absolute-address relocations")

    original = export(host, "WinHttpSetOption")
    query = export(host, "WinHttpQueryOption")
    replacement = export(helper, "http_set_option")
    state = export(helper, "adapter_state")
    imports = {}
    for library in host.DIRECTORY_ENTRY_IMPORT:
        if library.dll.lower() not in (b"kernel32.dll", b"kernelbase.dll"):
            continue
        for symbol in library.imports:
            if symbol.name:
                imports[symbol.name.decode()] = symbol.address - host.OPTIONAL_HEADER.ImageBase

    first_rva = min(section.VirtualAddress for section in helper.sections)
    payload = bytearray(helper.OPTIONAL_HEADER.SizeOfImage - first_rva)
    for section in helper.sections:
        offset = section.VirtualAddress - first_rva
        data = section.get_data()
        if offset + len(data) > len(payload):
            raise ValueError("Helper section extends beyond its image")
        payload[offset:offset + len(data)] = data

    section_alignment = host.OPTIONAL_HEADER.SectionAlignment
    file_alignment = host.OPTIONAL_HEADER.FileAlignment
    section_rva = align(max(s.VirtualAddress + max(s.Misc_VirtualSize, s.SizeOfRawData)
                            for s in host.sections), section_alignment)
    delta = section_rva - first_rva
    struct.pack_into("<IIIII", payload, state.address - first_rva,
                     state.address + delta, original.address, query.address,
                     imports["GetModuleHandleW"], imports["GetProcAddress"])

    # Preserve every host unwind record. Relocate helper records and their
    # unwind pointers; no chained records or exception handlers are supported.
    exception = host.OPTIONAL_HEADER.DATA_DIRECTORY[3]
    if exception.Size % 12:
        raise ValueError("Malformed host exception table")
    original_records = list(struct.iter_unpack(
        "<III", host.get_data(exception.VirtualAddress, exception.Size)))
    records = original_records.copy()
    for entry in getattr(helper, "DIRECTORY_ENTRY_EXCEPTION", []):
        record = entry.struct
        if helper.get_data(record.UnwindData, 1)[0] >> 3:
            raise ValueError("Helper unwind handlers/chains require relocation support")
        records.append((record.BeginAddress + delta, record.EndAddress + delta,
                        record.UnwindData + delta))
    records.sort()
    for previous, current in zip(records, records[1:]):
        if previous[1] > current[0]:
            raise ValueError("Overlapping exception-table functions")
    table_offset = align(len(payload), 4)
    payload.extend(bytes(table_offset - len(payload)))
    payload.extend(b"".join(struct.pack("<III", *record) for record in records))

    section_header = host.sections[-1].get_file_offset() + 40
    first_raw = min(s.PointerToRawData for s in host.sections if s.SizeOfRawData)
    if section_header + 40 > min(first_raw, host.OPTIONAL_HEADER.SizeOfHeaders):
        raise ValueError("No header space for an adapter section")
    if any(source_bytes[section_header:section_header + 40]):
        raise ValueError("Adapter section header would overwrite existing data")
    raw_offset = align(len(source_bytes), file_alignment)
    raw_size = align(len(payload), file_alignment)
    host.FILE_HEADER.NumberOfSections += 1
    host.OPTIONAL_HEADER.SizeOfImage = align(section_rva + len(payload), section_alignment)
    host.OPTIONAL_HEADER.SizeOfCode += raw_size
    exception.VirtualAddress = section_rva + table_offset
    exception.Size = len(records) * 12
    host.set_dword_at_offset(original.address_offset, replacement.address + delta)
    result = bytearray(host.write())
    struct.pack_into("<8sIIIIIIHHI", result, section_header, b".httpfix",
                     len(payload), section_rva, raw_size, raw_offset,
                     0, 0, 0, 0, 0x60000020)
    result.extend(bytes(raw_offset - len(result)))
    result.extend(payload)
    result.extend(bytes(raw_size - len(payload)))

    # Otherwise Wine redirects an n,b override back to its stock builtin.
    if result[0x40:0x60] != b"Wine builtin DLL".ljust(32, b"\0"):
        raise ValueError("Expected Wine builtin marker in source")
    result[0x40:0x60] = b"Private HTTP DLL".ljust(32, b"\0")
    patched = pefile.PE(data=result)
    patched.OPTIONAL_HEADER.CheckSum = patched.generate_checksum()
    result = patched.write()
    check = pefile.PE(data=result)
    assert export(check, "WinHttpSetOption").address == replacement.address + delta
    assert export(check, "WinHttpQueryOption").address == query.address
    checked_records = {(e.struct.BeginAddress, e.struct.EndAddress, e.struct.UnwindData)
                       for e in check.DIRECTORY_ENTRY_EXCEPTION}
    assert set(original_records) <= checked_records
    assert len(check.DIRECTORY_ENTRY_EXCEPTION) == len(records)
    original_offset = host.get_offset_from_rva(original.address)
    assert result[original_offset:original_offset + 32] == source_bytes[original_offset:original_offset + 32]
    args.output.write_bytes(result)

    manifest = {
        "source": args.source.name,
        "source_sha256": hashlib.sha256(source_bytes).hexdigest(),
        "adapter_sha256": hashlib.sha256(helper_bytes).hexdigest(),
        "output_sha256": hashlib.sha256(result).hexdigest(),
        "original_set_option_rva": hex(original.address),
        "adapter_set_option_rva": hex(replacement.address + delta),
        "original_unwind_records": len(original_records),
        "patched_unwind_records": len(records),
        "scope": "Accept option 133 DWORD0 on valid sessions; preserve existing request support and every other original result",
        "last_error": "Success clears LastError, following Wine WinHttpSetOption; fallback preserves original result/error",
    }
    args.output.with_suffix(".json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
