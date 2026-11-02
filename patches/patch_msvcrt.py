#!/usr/bin/env python3
"""Add the standard-stream adapter to a private copy of Wine's msvcrt.dll."""

import argparse
import hashlib
import json
from pathlib import Path
import struct

import pefile


def align(value, alignment):
    return (value + alignment - 1) // alignment * alignment


def export(pe, name):
    for symbol in pe.DIRECTORY_ENTRY_EXPORT.symbols:
        if symbol.name == name.encode():
            if symbol.forwarder:
                raise ValueError(f"{name} is a forwarded export")
            return symbol
    raise ValueError(f"Missing export: {name}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("adapter", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError(args.output)

    source_bytes = args.source.read_bytes()
    adapter_bytes = args.adapter.read_bytes()
    host = pefile.PE(data=source_bytes)
    helper = pefile.PE(data=adapter_bytes)
    for pe in (host, helper):
        if pe.FILE_HEADER.Machine != 0x8664 or pe.OPTIONAL_HEADER.Magic != 0x20B:
            raise ValueError("Both inputs must be x86-64 PE32+ DLLs")
        if not pe.FILE_HEADER.Characteristics & 0x2000:
            raise ValueError("Input is not a DLL")
    if any(s.Name.rstrip(b"\0") == b".crtfix" for s in host.sections):
        raise ValueError("The source already contains this adapter")
    if host.OPTIONAL_HEADER.DATA_DIRECTORY[4].Size:
        raise ValueError("Refusing to patch an Authenticode-signed runtime")
    if getattr(helper, "DIRECTORY_ENTRY_IMPORT", []):
        raise ValueError("Adapter must have no DLL imports")
    for block in getattr(helper, "DIRECTORY_ENTRY_BASERELOC", []):
        if any(entry.type for entry in block.entries):
            raise ValueError("Adapter contains absolute-address relocations")

    original = export(host, "freopen_s")
    replacement = export(helper, "crt_freopen_s")
    state = export(helper, "adapter_state")
    imports = {}
    for library in host.DIRECTORY_ENTRY_IMPORT:
        if library.dll.lower() not in (b"kernel32.dll", b"kernelbase.dll"):
            continue
        for symbol in library.imports:
            if symbol.name:
                imports[symbol.name.decode()] = symbol.address - host.OPTIONAL_HEADER.ImageBase

    first_rva = min(section.VirtualAddress for section in helper.sections)
    helper_end = helper.OPTIONAL_HEADER.SizeOfImage
    payload = bytearray(helper_end - first_rva)
    for section in helper.sections:
        offset = section.VirtualAddress - first_rva
        data = section.get_data()
        payload[offset:offset + len(data)] = data

    section_alignment = host.OPTIONAL_HEADER.SectionAlignment
    file_alignment = host.OPTIONAL_HEADER.FileAlignment
    section_rva = align(max(s.VirtualAddress + max(s.Misc_VirtualSize, s.SizeOfRawData)
                            for s in host.sections), section_alignment)
    delta = section_rva - first_rva
    struct.pack_into("<IIII", payload, state.address - first_rva,
                     state.address + delta, original.address,
                     imports["GetModuleHandleW"], imports["GetProcAddress"])

    # Keep the original exception records and add the adapter's relocated
    # records. Unwind metadata matters when a runtime function raises an error.
    exception = host.OPTIONAL_HEADER.DATA_DIRECTORY[3]
    if exception.Size % 12:
        raise ValueError("Malformed host exception table")
    records = list(struct.iter_unpack("<III", host.get_data(exception.VirtualAddress, exception.Size)))
    for entry in getattr(helper, "DIRECTORY_ENTRY_EXCEPTION", []):
        record = entry.struct
        if helper.get_data(record.UnwindData, 1)[0] >> 3:
            raise ValueError("Adapter unwind handlers or chained records need relocation support")
        records.append((record.BeginAddress + delta, record.EndAddress + delta,
                        record.UnwindData + delta))
    records.sort()
    for previous, current in zip(records, records[1:]):
        if previous[1] > current[0]:
            raise ValueError("Overlapping function entries in exception table")
    table_offset = align(len(payload), 4)
    payload.extend(bytes(table_offset - len(payload)))
    payload.extend(b"".join(struct.pack("<III", *record) for record in records))

    section_header = host.sections[-1].get_file_offset() + 40
    first_raw = min(s.PointerToRawData for s in host.sections if s.SizeOfRawData)
    if section_header + 40 > first_raw or any(source_bytes[section_header:section_header + 40]):
        raise ValueError("No unused header slot for the adapter section")
    raw_offset = align(len(source_bytes), file_alignment)
    raw_size = align(len(payload), file_alignment)

    host.FILE_HEADER.NumberOfSections += 1
    host.OPTIONAL_HEADER.SizeOfImage = align(section_rva + len(payload), section_alignment)
    host.OPTIONAL_HEADER.SizeOfCode += raw_size
    exception.VirtualAddress = section_rva + table_offset
    exception.Size = len(records) * 12
    host.set_dword_at_offset(original.address_offset, replacement.address + delta)
    result = bytearray(host.write())
    struct.pack_into("<8sIIIIIIHHI", result, section_header, b".crtfix\0",
                     len(payload), section_rva, raw_size, raw_offset,
                     0, 0, 0, 0, 0x60000020)
    result.extend(bytes(raw_offset - len(result)))
    result.extend(payload)
    result.extend(bytes(raw_size - len(payload)))

    # Wine replaces a marked builtin with its runner copy even for an n,b
    # override. This private PE must load as the explicitly selected DLL.
    if result[0x40:0x60] != b"Wine builtin DLL".ljust(32, b"\0"):
        raise ValueError("Expected Wine builtin DLL marker in source")
    result[0x40:0x60] = b"Private CRT DLL".ljust(32, b"\0")

    patched = pefile.PE(data=result)
    patched.OPTIONAL_HEADER.CheckSum = patched.generate_checksum()
    result = patched.write()
    check = pefile.PE(data=result)
    assert export(check, "freopen_s").address == replacement.address + delta
    assert len(check.DIRECTORY_ENTRY_EXCEPTION) == len(records)
    original_offset = host.get_offset_from_rva(original.address)
    assert result[original_offset:original_offset + 32] == source_bytes[original_offset:original_offset + 32]
    args.output.write_bytes(result)

    manifest = {
        "source": args.source.name,
        "source_sha256": hashlib.sha256(source_bytes).hexdigest(),
        "adapter_sha256": hashlib.sha256(adapter_bytes).hexdigest(),
        "output_sha256": hashlib.sha256(result).hexdigest(),
        "original_freopen_s_rva": hex(original.address),
        "adapter_freopen_s_rva": hex(replacement.address + delta),
        "scope": "Wine standard-stream CRT interoperability; original game files unchanged",
    }
    args.output.with_suffix(".json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
