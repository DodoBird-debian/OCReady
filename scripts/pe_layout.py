"""Read only PE headers to diagnose Windows executable layout and size limits."""
import struct
from pathlib import Path


def inspect_pe(path: Path) -> dict:
    file_size = path.stat().st_size
    with path.open("rb") as stream:
        dos = stream.read(64)
        if len(dos) != 64 or dos[:2] != b"MZ":
            raise ValueError("The Windows output has no DOS/PE header.")
        offset = struct.unpack_from("<I", dos, 60)[0]
        if offset < 64 or offset > min(file_size - 24, 1_000_000):
            raise ValueError("The PE header offset is invalid.")
        stream.seek(offset)
        header = stream.read(24)
        if len(header) != 24 or header[:4] != b"PE\x00\x00":
            raise ValueError("The Windows output has an invalid PE signature.")
        machine, count = struct.unpack_from("<HH", header, 4)
        optional_size = struct.unpack_from("<H", header, 20)[0]
        if not 1 <= count <= 2048 or optional_size < 64:
            raise ValueError("The PE section/optional header is invalid.")
        optional = stream.read(optional_size)
        if len(optional) != optional_size or struct.unpack_from("<H", optional)[0] != 0x20B:
            raise ValueError("Expected a PE32+ executable.")
        image_size = struct.unpack_from("<I", optional, 56)[0]
        if not image_size:
            raise ValueError("The PE mapped image size is zero.")
        sections = []
        for _ in range(count):
            section = stream.read(40)
            if len(section) != 40:
                raise ValueError("The PE section table is truncated.")
            virtual_size, address, raw_size, raw_offset = struct.unpack_from("<IIII", section, 8)
            if raw_size and raw_offset + raw_size > file_size:
                raise ValueError("A PE section extends past the executable file.")
            if address + max(virtual_size, raw_size) > image_size:
                raise ValueError("A PE section extends past the mapped image.")
            sections.append({"name": section[:8].rstrip(b"\x00").decode("ascii", errors="replace"),
                             "virtual_size": virtual_size, "virtual_address": address,
                             "raw_size": raw_size, "raw_offset": raw_offset})
    return {"file_bytes": file_size, "machine": hex(machine), "image_bytes": image_size, "sections": sections,
            "pe32_plus_under_2gib": image_size < 2 ** 31}
