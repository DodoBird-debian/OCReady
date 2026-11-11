"""Give OCReady's copied native OCR executable a per-process UTF-8 manifest."""
import ctypes
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

ASM1 = "urn:schemas-microsoft-com:asm.v1"
ASM3 = "urn:schemas-microsoft-com:asm.v3"
SETTINGS = "http://schemas.microsoft.com/SMI/2019/WindowsSettings"


def utf8_manifest(original: bytes | None) -> bytes:
    ET.register_namespace("", ASM1)
    ET.register_namespace("asmv3", ASM3)
    ET.register_namespace("ws2019", SETTINGS)
    root = ET.fromstring(original) if original else ET.Element(f"{{{ASM1}}}assembly", manifestVersion="1.0")
    if root.tag != f"{{{ASM1}}}assembly":
        raise ValueError("Unexpected native executable manifest root")
    application = root.find(f"{{{ASM3}}}application")
    if application is None:
        application = ET.SubElement(root, f"{{{ASM3}}}application")
    settings = application.find(f"{{{ASM3}}}windowsSettings")
    if settings is None:
        settings = ET.SubElement(application, f"{{{ASM3}}}windowsSettings")
    codepage = settings.find(f"{{{SETTINGS}}}activeCodePage")
    if codepage is None:
        codepage = ET.SubElement(settings, f"{{{SETTINGS}}}activeCodePage")
    codepage.text = "UTF-8"
    return ET.tostring(root, encoding="utf-8", xml_declaration=True)


def enable_utf8_paths(executable: Path) -> list[bytes]:
    """Update manifest resource #1, preserving languages and other resources.

    LoadLibraryEx uses data-file/image-resource flags, so no native code runs.
    Call only on the private copy in runtime/bin, never the installed engine.
    """
    if sys.platform != "win32":
        raise RuntimeError("Native resource updates require Windows")
    from ctypes import wintypes as W
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    pointer = ctypes.c_void_p
    signatures = {
        "LoadLibraryExW": ([W.LPCWSTR, W.HANDLE, W.DWORD], W.HMODULE),
        "FreeLibrary": ([W.HMODULE], W.BOOL),
        "FindResourceExW": ([W.HMODULE, pointer, pointer, W.WORD], W.HRSRC),
        "LoadResource": ([W.HMODULE, W.HRSRC], W.HGLOBAL),
        "SizeofResource": ([W.HMODULE, W.HRSRC], W.DWORD),
        "LockResource": ([W.HGLOBAL], pointer),
        "BeginUpdateResourceW": ([W.LPCWSTR, W.BOOL], W.HANDLE),
        "UpdateResourceW": ([W.HANDLE, pointer, pointer, W.WORD, pointer, W.DWORD], W.BOOL),
        "EndUpdateResourceW": ([W.HANDLE, W.BOOL], W.BOOL),
    }
    for name, (arguments, result) in signatures.items():
        function = getattr(kernel, name)
        function.argtypes, function.restype = arguments, result
    callback_type = ctypes.WINFUNCTYPE(W.BOOL, W.HMODULE, pointer, pointer, W.WORD, ctypes.c_ssize_t)
    kernel.EnumResourceLanguagesW.argtypes = [W.HMODULE, pointer, pointer, callback_type, ctypes.c_ssize_t]
    kernel.EnumResourceLanguagesW.restype = W.BOOL
    module = kernel.LoadLibraryExW(str(executable.resolve()), None, 0x2 | 0x20)
    if not module:
        raise ctypes.WinError(ctypes.get_last_error())
    languages = []
    records = []
    @callback_type
    def collect(_module, _type, _name, language, _parameter):
        languages.append(language)
        return True
    try:
        if not kernel.EnumResourceLanguagesW(module, pointer(24), pointer(1), collect, 0):
            error = ctypes.get_last_error()
            if error not in {1812, 1813, 1814, 1815}:
                raise ctypes.WinError(error)
        for language in languages:
            resource = kernel.FindResourceExW(module, pointer(24), pointer(1), language)
            if not resource:
                raise ctypes.WinError(ctypes.get_last_error())
            size = kernel.SizeofResource(module, resource)
            data = kernel.LockResource(kernel.LoadResource(module, resource))
            if not data or not 0 < size <= 1_000_000:
                raise RuntimeError("Could not read the native executable manifest")
            records.append((language, utf8_manifest(ctypes.string_at(data, size))))
    finally:
        kernel.FreeLibrary(module)
    if not records:
        records = [(0, utf8_manifest(None))]
    update = kernel.BeginUpdateResourceW(str(executable.resolve()), False)
    if not update:
        raise ctypes.WinError(ctypes.get_last_error())
    committed = False
    try:
        for language, manifest in records:
            buffer = ctypes.create_string_buffer(manifest)
            if not kernel.UpdateResourceW(update, pointer(24), pointer(1), language, buffer, len(manifest)):
                raise ctypes.WinError(ctypes.get_last_error())
        if not kernel.EndUpdateResourceW(update, False):
            raise ctypes.WinError(ctypes.get_last_error())
        committed = True
    finally:
        if not committed:
            kernel.EndUpdateResourceW(update, True)
    return [manifest for _, manifest in records]
