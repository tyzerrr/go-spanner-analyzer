#!/usr/bin/env python3
"""build.json を wasi-sdk で再生できる形に直す。`wasmify generate-build` の後に、
Bazel の実行ルートが見える場所（コンテナ内）で実行する。

1. wasi-sdk の clang が受け付けない GCC 専用フラグを落とす
2. 差分ビルドで誤って wasm_skip にされた手順を戻す
   （wasmify は「出力の更新時刻がビルド開始より古い」と一時的な成果物と見なして
    skip するが、Bazel の差分ビルドでは触られなかった出力がすべてそれに当たる。
    出力ファイルが実在すれば skip を外す）"""
import json, os, sys
GCC_ONLY = {"-fno-canonical-system-headers"}
PROBE = "transient probe artifact"
p = sys.argv[1] if len(sys.argv) > 1 else "build.json"
d = json.load(open(p))
flags_removed = unskipped = still_missing = 0
for s in d.get("steps", []):
    n = len(s.get("args", []))
    s["args"] = [a for a in s.get("args", []) if a not in GCC_ONLY]
    flags_removed += n - len(s["args"])
    if s.get("wasm_skip") and PROBE in s.get("wasm_skip_reason", ""):
        out = s.get("output_file", "")
        path = out if os.path.isabs(out) else os.path.join(s.get("work_dir", ""), out)
        if out and os.path.exists(path):
            s["wasm_skip"] = False
            s.pop("wasm_skip_reason", None)
            unskipped += 1
        else:
            still_missing += 1
json.dump(d, open(p, "w"), indent=2)
print(f"fix_build_json: flags removed={flags_removed}, unskipped={unskipped}, still missing={still_missing}, "
      f"remaining skip={sum(1 for s in d['steps'] if s.get('wasm_skip'))}/{len(d['steps'])}")
