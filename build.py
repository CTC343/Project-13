"""Build the two Windows clients with MSVC and the selected x64 Python OpenSSL 3 DLLs."""

import argparse
import os
from pathlib import Path
import re
import shutil
import ssl
import subprocess
import sys
from tempfile import TemporaryDirectory

ROOT = Path(__file__).resolve().parent


def vcvars():
    if override := os.environ.get("PROJECT13_VCVARS"):
        return Path(override)
    installer = Path("Microsoft Visual Studio/Installer/vswhere.exe")
    candidates = [
        Path(os.environ.get("ProgramFiles(x86)", "")) / installer,
        Path(os.environ.get("SystemDrive", "C:") + "/Program Files (x86)") / installer,
    ]
    vswhere = next((candidate for candidate in candidates if candidate.is_file()), None)
    if vswhere is None:
        raise RuntimeError("Set PROJECT13_VCVARS to the path to vcvars64.bat.")
    install = subprocess.check_output([
        str(vswhere), "-latest", "-products", "*", "-requires",
        "Microsoft.VisualStudio.Component.VC.Tools.x86.x64", "-property", "installationPath",
    ], encoding="utf-8").strip()
    if not install:
        raise RuntimeError("Install Visual Studio Build Tools with Desktop development with C++.")
    return Path(install) / "VC/Auxiliary/Build/vcvars64.bat"


def build(output):
    if os.name != "nt" or sys.maxsize <= 2**32 or ssl.OPENSSL_VERSION_INFO[0] != 3:
        raise RuntimeError("Use 64-bit Windows Python linked with OpenSSL 3.")
    dll_dir = Path(sys.base_prefix) / "DLLs"
    dlls = {}
    for stem in ("libssl", "libcrypto"):
        dlls[stem] = next((path for path in dll_dir.glob(f"{stem}-3*.dll") if path.is_file()), None)
        if dlls[stem] is None:
            raise RuntimeError(f"Missing {stem} OpenSSL runtime in {dll_dir}")
    tools = vcvars()
    sources = ROOT / "client"
    declarations = (sources / "openssl_api.h").read_text(encoding="utf-8")
    exports = re.findall(r"\b((?:SSL|TLS|X509|EVP|BIO|PEM|ERR)\w+)\(", declarations)
    with TemporaryDirectory(prefix="p13-build-") as temporary:
        stage = Path(temporary)
        commands = [f'call "{tools}" >nul']
        for library, dll in dlls.items():
            symbols = [name for name in exports
                       if name.startswith(("X509_", "EVP_", "BIO_", "PEM_", "ERR_")) == (library == "libcrypto")]
            (stage / f"{library}.def").write_text(
                f"LIBRARY {dll.name}\nEXPORTS\n" + "\n".join(symbols), encoding="ascii"
            )
            commands.append(f"lib /nologo /machine:x64 /def:{library}.def /out:{library}.lib")
        common = [
            str(sources / name) for name in (
                "client_logic.c", "credentials.c", "device.c", "merkle.c", "network.c", "operations.c",
                "outbox.c", "protocol.c", "security.c", "signature.c",
            )
        ]
        for name, extra in (
            ("client", []),
            ("client_gui", [str(sources / "watchdog.c"), str(sources / "preview.c"),
                            "ole32.lib", "windowscodecs.lib", "uuid.lib"]),
        ):
            arguments = [
                "cl", "/nologo", "/std:c11", "/utf-8", "/D_CRT_SECURE_NO_WARNINGS",
                "/O2", "/MT", "/W3", f"/Fe:{name}.exe",
                str(sources / f"{name}.c"), *common, *extra,
                "libssl.lib", "libcrypto.lib", "ws2_32.lib", "bcrypt.lib",
                "crypt32.lib", "user32.lib", "gdi32.lib",
            ]
            commands.append(subprocess.list2cmdline(arguments))
        subprocess.run(" && ".join(commands), cwd=stage, shell=True, check=True)
        output.mkdir(parents=True, exist_ok=True)
        for name in ("client.exe", "client_gui.exe"):
            shutil.copy2(stage / name, output / name)
        for path in (*dlls.values(), *Path(sys.base_prefix).glob("vcruntime140*.dll")):
            shutil.copy2(path, output / path.name)
        for name in ("LICENSE.txt", "LICENSE"):
            license_file = Path(sys.base_prefix) / name
            if license_file.is_file():
                shutil.copy2(license_file, output / "runtime-LICENSE.txt")
                break
    print(f"Built both clients in {output}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=ROOT / "client/output")
    build(parser.parse_args().output.resolve())
