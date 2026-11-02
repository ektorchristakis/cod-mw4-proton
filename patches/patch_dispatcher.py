#!/usr/bin/env python3
"""Use Windows-compatible argument-setup encoding in a private Wine dispatcher.

This changes instruction layout only. Wine's exception handler, disposition,
and continuation behavior remain unchanged.
"""

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
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError(args.output)
    original_bytes = args.source.read_bytes()
    pe = pefile.PE(data=original_bytes)
    if pe.FILE_HEADER.Machine != 0x8664 or pe.OPTIONAL_HEADER.Magic != 0x20B:
        raise ValueError("Expected x86-64 Wine ntdll")
    if pe.OPTIONAL_HEADER.DATA_DIRECTORY[4].Size:
        raise ValueError("Refusing to patch a signed library")
    symbol = export(pe, "KiUserExceptionDispatcher")
    code = pe.get_data(symbol.address, 43)
    if (code[:4] != bytes.fromhex("fc488b05") or
            code[8:37] != bytes.fromhex(
                "4885c0740d4889e2488d8c24f0040000ffd0"
                "4889e2488d8c24f0040000") or code[37] != 0xe8 or code[42] != 0xcc):
        raise ValueError("Dispatcher does not match the verified Wine layout")
    pointer_rva = symbol.address + 8 + struct.unpack_from("<i", code, 4)[0]
    target_rva = symbol.address + 42 + struct.unpack_from("<i", code, 38)[0]
    original_entry = next(e.struct for e in pe.DIRECTORY_ENTRY_EXCEPTION
                          if e.struct.BeginAddress == symbol.address)
    if original_entry.EndAddress != symbol.address + 43:
        raise ValueError("Unexpected dispatcher unwind range")
    unwind = pe.get_data(original_entry.UnwindData, 4)
    if unwind[1] != 0:
        raise ValueError("Only zero-length dispatcher prologues are supported")

    section_rva = align(max(s.VirtualAddress + max(s.Misc_VirtualSize, s.SizeOfRawData)
                            for s in pe.sections), pe.OPTIONAL_HEADER.SectionAlignment)
    text_section = next(s for s in pe.sections if s.Name.rstrip(b"\0") == b".text")
    clone_rva = align(text_section.VirtualAddress + text_section.Misc_VirtualSize, 16)
    clone_offset = clone_rva - text_section.VirtualAddress
    if (clone_offset + 47 > text_section.SizeOfRawData or
            any(text_section.get_data()[clone_offset:clone_offset + 47])):
        raise ValueError("No unused executable padding for dispatcher")
    # The caller also decodes the pWow64 reference without sign extension.
    # Keep code before its data, as in both original Wine and Windows images.
    if pointer_rva < clone_rva + 8:
        raise ValueError("Dispatcher data must follow its code")
    # mov rcx,rsp; add rcx,0x4f0; mov rdx,rsp computes exactly the
    # same arguments as Wine's mov rdx,rsp; lea rcx,[rsp+0x4f0].
    setup = bytes.fromhex("488bcc4881c1f0040000488bd4")
    clone = bytearray(bytes.fromhex("fc488b05") +
                        struct.pack("<i", pointer_rva - (clone_rva + 8)) +
                        bytes.fromhex("4885c0740f") + setup +
                        bytes.fromhex("ffd0") + setup + b"\xe8" +
                        struct.pack("<i", target_rva - (clone_rva + 46)) + b"\xcc")
    assert len(clone) == 47 and clone[41] == 0xe8
    exception = pe.OPTIONAL_HEADER.DATA_DIRECTORY[3]
    records = list(struct.iter_unpack("<III", pe.get_data(exception.VirtualAddress, exception.Size)))
    records.append((clone_rva, clone_rva + len(clone), original_entry.UnwindData))
    records.sort()
    payload = bytearray(b"".join(struct.pack("<III", *r) for r in records))

    header = pe.sections[-1].get_file_offset() + 40
    first_raw = min(s.PointerToRawData for s in pe.sections if s.SizeOfRawData)
    if header + 40 > first_raw or any(original_bytes[header:header + 40]):
        raise ValueError("No spare section header")
    raw_offset = align(len(original_bytes), pe.OPTIONAL_HEADER.FileAlignment)
    raw_size = align(len(payload), pe.OPTIONAL_HEADER.FileAlignment)
    pe.FILE_HEADER.NumberOfSections += 1
    pe.OPTIONAL_HEADER.SizeOfImage = align(section_rva + len(payload), pe.OPTIONAL_HEADER.SectionAlignment)
    pe.OPTIONAL_HEADER.SizeOfInitializedData += raw_size
    exception.VirtualAddress = section_rva
    exception.Size = len(records) * 12
    pe.set_dword_at_offset(symbol.address_offset, clone_rva)
    pe.set_bytes_at_rva(clone_rva, bytes(clone))
    text_section.Misc_VirtualSize = clone_offset + len(clone)
    result = bytearray(pe.write())
    struct.pack_into("<8sIIIIIIHHI", result, header, b".sehfix\0", len(payload),
                     section_rva, raw_size, raw_offset, 0, 0, 0, 0, 0x40000040)
    result.extend(bytes(raw_offset - len(result)))
    result.extend(payload)
    result.extend(bytes(raw_size - len(payload)))
    patched = pefile.PE(data=result)
    patched.OPTIONAL_HEADER.CheckSum = patched.generate_checksum()
    result = patched.write()
    check = pefile.PE(data=result)
    assert export(check, "KiUserExceptionDispatcher").address == clone_rva
    assert check.get_data(clone_rva, len(clone)) == clone
    assert check.get_data(symbol.address, 43) == code
    assert len(check.DIRECTORY_ENTRY_EXCEPTION) == len(records)
    args.output.write_bytes(result)
    manifest = dict(source_sha256=hashlib.sha256(original_bytes).hexdigest(),
                    output_sha256=hashlib.sha256(result).hexdigest(),
                    original_rva=hex(symbol.address), new_rva=hex(clone_rva),
                    unchanged_handler_rva=hex(target_rva))
    args.output.with_suffix(".json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
