import importlib.metadata
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from scripts.payload_memory import CALL_MARKER, INCLUDE_MARKER, compiler_overlay, patch_bootstrap
from scripts.provenance import file_sha256


def test_compiler_overlay_leaves_installed_tool_unchanged_even_on_failure(tmp_path):
    import nuitka
    bootstrap = Path(nuitka.__file__).parent / "build/static_src/OnefileBootstrap.c"
    original = file_sha256(bootstrap)
    with pytest.raises(RuntimeError, match="simulated build failure"):
        with compiler_overlay(tmp_path) as (overlay, metadata):
            assert metadata["enabled"]
            assert metadata["original_bootstrap_sha256"] == original
            assert file_sha256(bootstrap) == original
            assert file_sha256(overlay / "nuitka/build/static_src/OnefileBootstrap.c") != original
            raise RuntimeError("simulated build failure")
    assert file_sha256(bootstrap) == original
    assert not list(tmp_path.iterdir())


def test_unknown_bootstrap_or_compiler_is_rejected(tmp_path, monkeypatch):
    with pytest.raises(RuntimeError, match="layout changed"):
        patch_bootstrap("unknown source", "header")
    patched = patch_bootstrap(INCLUDE_MARKER + CALL_MARKER, "/* helper */")
    assert "ocready_release_payload_pages(payload_data, payload_size)" in patched
    monkeypatch.setattr(importlib.metadata, "version", lambda _name: "future-version")
    with pytest.raises(RuntimeError, match="verified for Nuitka"):
        with compiler_overlay(tmp_path):
            pass


@pytest.mark.skipif(sys.platform != "linux" or not shutil.which("cc"), reason="Native Linux mapping test")
def test_payload_release_preserves_file_contents_and_reduces_own_rss(tmp_path):
    header = Path(__file__).resolve().parents[1] / "native/payload_memory.h"
    data = tmp_path / "data"
    with data.open("wb") as stream:
        for _ in range(4096):
            stream.write(b"A" * 4096)
    source = tmp_path / "probe.c"
    source.write_text(r'''
#define _GNU_SOURCE
#include <stdio.h>
#include <fcntl.h>
#include <assert.h>
#include "payload_memory.h"
static long resident(void) {
    long pages=0, total=0;
    FILE *f=fopen("/proc/self/statm", "r");
    assert(f && fscanf(f, "%ld %ld", &total, &pages)==2);
    fclose(f);
    return pages*sysconf(_SC_PAGESIZE);
}
int main(int argc, char **argv) {
    (void)argc;
    const size_t size=16*1024*1024;
    int fd=open(argv[1], O_RDONLY);
    assert(fd>=0);
    const unsigned char *data=mmap(NULL,size,PROT_READ,MAP_PRIVATE,fd,0);
    assert(data!=MAP_FAILED);
    volatile unsigned int sum=0;
    for (size_t i=0;i<size;i+=4096) sum+=data[i];
    assert(sum==65*(size/4096));
    long before=resident();
    ocready_release_payload_pages(data,size);
    long after=resident();
    assert(after+size/2<before);
    assert(data[0]==65 && data[size-1]==65);
    munmap((void *)data,size);
    close(fd);
    return 0;
}
''', encoding="utf-8")
    executable = tmp_path / "probe"
    subprocess.run(["cc", "-std=c11", "-I", str(header.parent), str(source), "-o", str(executable)], check=True, capture_output=True)
    subprocess.run([str(executable), str(data)], check=True, capture_output=True)
