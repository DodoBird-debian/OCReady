import struct

import pytest

from scripts.pe_layout import inspect_pe


def executable(tmp_path, image_size=8192):
    data = bytearray(1024)
    data[:2] = b"MZ"
    struct.pack_into("<I", data, 60, 128)
    data[128:132] = b"PE\x00\x00"
    struct.pack_into("<HH", data, 132, 0x8664, 1)
    struct.pack_into("<H", data, 148, 240)
    optional = 152
    struct.pack_into("<H", data, optional, 0x20B)
    struct.pack_into("<I", data, optional + 56, image_size)
    section = optional + 240
    data[section:section + 6] = b".rdata"
    struct.pack_into("<IIII", data, section + 8, 512, 4096, 512, 512)
    path = tmp_path / "program.exe"
    path.write_bytes(data)
    return path


def test_pe_layout_distinguishes_mapped_image_size_from_file_size(tmp_path):
    layout = inspect_pe(executable(tmp_path))
    assert layout["machine"] == "0x8664" and layout["image_bytes"] == 8192
    assert layout["file_bytes"] == 1024 and layout["pe32_plus_under_2gib"]
    layout = inspect_pe(executable(tmp_path, 2 ** 31))
    assert not layout["pe32_plus_under_2gib"]


def test_pe_audit_rejects_truncated_or_invalid_executables(tmp_path):
    path = executable(tmp_path)
    path.write_bytes(path.read_bytes()[:400])
    with pytest.raises(ValueError):
        inspect_pe(path)
    path.write_bytes(b"not an executable")
    with pytest.raises(ValueError, match="header"):
        inspect_pe(path)


@pytest.mark.parametrize("size", [0, 4096])
def test_pe_audit_rejects_missing_or_undersized_mapped_image(tmp_path, size):
    with pytest.raises(ValueError, match="image"):
        inspect_pe(executable(tmp_path, size))


def test_pe_audit_records_native_icon_resource_types(tmp_path):
    path = executable(tmp_path)
    data = bytearray(path.read_bytes())
    optional = 152
    struct.pack_into("<I", data, optional + 108, 16)
    struct.pack_into("<II", data, optional + 128, 4096, 64)
    struct.pack_into("<HH", data, 512 + 12, 0, 3)
    for index, kind in enumerate((3, 14, 16)):
        struct.pack_into("<II", data, 528 + index * 8, kind, 0x80000028)
    path.write_bytes(data)
    assert inspect_pe(path)["resource_types"] == [3, 14, 16]
    struct.pack_into("<I", data, optional + 132, 20)
    path.write_bytes(data)
    with pytest.raises(ValueError, match="resource table"):
        inspect_pe(path)
