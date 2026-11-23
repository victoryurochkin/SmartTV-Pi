#!/usr/bin/env bash
set -euo pipefail
cd -- "$(dirname -- "$0")/.."

git diff --check
for path in build/*.sh build/runtime/usr/lib/home-tv/data-grow; do
    bash -n "$path"
done
python3 - <<'PYTHON'
import ast
import json
from pathlib import Path
import xml.etree.ElementTree as ET

for path in Path("rootfs").rglob("*"):
    if not path.is_file():
        continue
    if path.suffix == ".xml":
        ET.parse(path)
    elif path.suffix == ".json":
        json.loads(path.read_text(encoding="utf-8"))
    else:
        with path.open("rb") as stream:
            shebang = stream.read(23)
        if path.suffix == ".py" or shebang.startswith((b"#!/usr/bin/env python3", b"#!/usr/bin/python3")):
            ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
PYTHON
while IFS= read -r -d '' path; do
    if head -n 1 "$path" | grep -Eq '^#!.*/(ba)?sh$'; then
        if head -n 1 "$path" | grep -q 'bash'; then
            bash -n "$path"
        else
            sh -n "$path"
        fi
    fi
done < <(find rootfs/usr/lib/home-tv -type f -print0)
python3 -m unittest discover -s tests
