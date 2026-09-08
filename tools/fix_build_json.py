#!/usr/bin/env python3
"""build.json から wasi-sdk の clang が受け付けない GCC 専用フラグを落とす。
`wasmify generate-build` の後に実行する。wasmify 側に除去の設定が無いための補助。"""
import json, sys
GCC_ONLY = {
    "-fno-canonical-system-headers",   # clang: unknown argument（致命的）
}
p = sys.argv[1] if len(sys.argv) > 1 else "build.json"
d = json.load(open(p))
removed = 0
for s in d.get("steps", []):
    before = len(s.get("args", []))
    s["args"] = [a for a in s.get("args", []) if a not in GCC_ONLY]
    removed += before - len(s["args"])
json.dump(d, open(p, "w"), indent=2)
print(f"fix_build_json: removed {removed} flag(s) from {p}")
