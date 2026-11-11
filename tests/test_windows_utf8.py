import xml.etree.ElementTree as ET

from scripts.windows_utf8 import ASM1, ASM3, SETTINGS, utf8_manifest


def test_utf8_manifest_preserves_execution_level_and_existing_windows_settings():
    original = f'''<assembly xmlns="{ASM1}" manifestVersion="1.0">
      <assemblyIdentity name="Original.Engine" version="5.5.0.0"/>
      <trustInfo xmlns="{ASM3}"><security><requestedPrivileges><requestedExecutionLevel level="asInvoker"/></requestedPrivileges></security></trustInfo>
      <application xmlns="{ASM3}"><windowsSettings><dpiAware xmlns="http://schemas.microsoft.com/SMI/2005/WindowsSettings">true</dpiAware></windowsSettings></application>
    </assembly>'''.encode()
    result = utf8_manifest(original)
    root = ET.fromstring(result)
    assert root.find(f"{{{ASM1}}}assemblyIdentity").get("name") == "Original.Engine"
    assert root.find(f".//{{{ASM3}}}requestedExecutionLevel").get("level") == "asInvoker"
    assert root.find(".//{http://schemas.microsoft.com/SMI/2005/WindowsSettings}dpiAware").text == "true"
    assert root.find(f"{{{ASM3}}}application/{{{ASM3}}}windowsSettings/{{{SETTINGS}}}activeCodePage").text == "UTF-8"
    assert utf8_manifest(result) == result


def test_utf8_manifest_can_be_added_to_an_executable_without_one():
    root = ET.fromstring(utf8_manifest(None))
    assert root.tag == f"{{{ASM1}}}assembly" and root.get("manifestVersion") == "1.0"
    assert root.find(f".//{{{SETTINGS}}}activeCodePage").text == "UTF-8"
