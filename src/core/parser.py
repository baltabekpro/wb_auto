import os
import re
from dataclasses import dataclass
from typing import Dict, List, Tuple

DEFAULT_PATTERN = r"^(?P<sku>.+)\.(?P<n>\d+)\.(?P<ext>jpe?g|png)$"

@dataclass
class PhotoFile:
    path: str
    sku: str
    n: int
    ext: str

@dataclass
class GroupResult:
    by_sku: Dict[str, List[PhotoFile]]
    warnings: List[str]
    errors: List[str]


def group_photos_flat(folder: str, pattern: str = DEFAULT_PATTERN) -> GroupResult:
    rx = re.compile(pattern, re.IGNORECASE)
    by_sku: Dict[str, List[PhotoFile]] = {}
    warnings: List[str] = []
    errors: List[str] = []

    for entry in os.listdir(folder):
        full = os.path.join(folder, entry)
        if not os.path.isfile(full):
            continue
        m = rx.match(entry)
        if not m:
            warnings.append(f"Skip not matching file: {entry}")
            continue
        sku = m.group('sku')
        n = int(m.group('n'))
        ext = m.group('ext').lower()
        pf = PhotoFile(path=full, sku=sku, n=n, ext=ext)
        by_sku.setdefault(sku, []).append(pf)

    # sort and detect duplicates/missing numbers
    for sku, files in by_sku.items():
        files.sort(key=lambda x: x.n)
        seen: Dict[int, PhotoFile] = {}
        for f in files:
            if f.n in seen:
                warnings.append(f"Duplicate index for {sku}: {f.n} -> {os.path.basename(seen[f.n].path)} and {os.path.basename(f.path)}")
            else:
                seen[f.n] = f
        if files:
            expected = list(range(files[0].n, files[-1].n + 1))
            missing = [i for i in expected if i not in seen]
            if missing:
                warnings.append(f"Missing indices for {sku}: {missing}")

    return GroupResult(by_sku=by_sku, warnings=warnings, errors=errors)
