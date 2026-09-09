#!/usr/bin/env python3
"""wasm2go の生成物を、Go モジュールの上限（1 モジュール 500 MiB）に収まる入れ子モジュールに分ける。

使い方: python3 tools/split_bundle.py <wasm2go 出力の internal/wasm2go> <公開先の作業木> <version>

wasm2go は生成物を base/ と p0/ .. pN/ に分けて出す。それぞれを独立したモジュールにし、
依存を root → pN → p(N-1) → ... → p0 → base の一方向に張る。import path は変えない。
公開先の README / LICENSE / NOTICE / THIRD_PARTY_NOTICES は残し、生成物だけを差し替える。
最後に、打つべきタグを依存の順に出力する（依存先を先にタグ付けしないと go get が解決できない）。
"""
import os
import re
import shutil
import sys

MODULE = "github.com/tyzerrr/spanneranalyzerwasm2go"
KEEP = {"README.md", "LICENSE", "NOTICE", "THIRD_PARTY_NOTICES.txt", ".git", ".gitignore"}


def parts(src):
    names = sorted(
        (n for n in os.listdir(src) if re.fullmatch(r"p\d+", n)),
        key=lambda n: int(n[1:]),
    )
    if not names:
        sys.exit(f"{src} に p0.. が見当たらない")
    return names


def write_go_mod(path, module, version, requires, go="1.25"):
    lines = [f"module {module}", "", f"go {go}", ""]
    if requires:
        lines.append("require (")
        lines += [f"\t{r} {version}" for r in requires]
        lines.append(")")
    with open(os.path.join(path, "go.mod"), "w") as f:
        f.write("\n".join(lines) + "\n")


def main():
    if len(sys.argv) != 4:
        sys.exit(__doc__)
    src, dst, version = sys.argv[1], sys.argv[2], sys.argv[3]
    if not re.fullmatch(r"v\d+\.\d+\.\d+", version):
        sys.exit(f"version は vX.Y.Z の形: {version}")

    ps = parts(src)

    # 公開先の生成物を消す（保持するものは残す）
    for name in os.listdir(dst):
        if name in KEEP:
            continue
        p = os.path.join(dst, name)
        shutil.rmtree(p) if os.path.isdir(p) else os.remove(p)

    # 生成物を複製する（wasm2go が書いた go.mod はこの後上書きする）
    for name in os.listdir(src):
        if name == "go.mod":
            continue
        s, d = os.path.join(src, name), os.path.join(dst, name)
        shutil.copytree(s, d) if os.path.isdir(s) else shutil.copy2(s, d)

    base = f"{MODULE}/base"
    write_go_mod(os.path.join(dst, "base"), base, version, [])
    prev = None
    for name in ps:
        requires = [base] + ([f"{MODULE}/{prev}"] if prev else [])
        write_go_mod(os.path.join(dst, name), f"{MODULE}/{name}", version, requires)
        prev = name
    write_go_mod(dst, MODULE, version, [base, f"{MODULE}/{ps[-1]}"])

    # 大きさの確認（500 MiB を超えるものがあれば止める）
    limit = 500 * 1024 * 1024
    for name in ["base"] + ps + ["."]:
        p = os.path.join(dst, name)
        size = 0
        for root, dirs, files in os.walk(p):
            if name == ".":
                dirs[:] = [d for d in dirs if d not in {"base", ".git"} and not re.fullmatch(r"p\d+", d)]
            size += sum(os.path.getsize(os.path.join(root, f)) for f in files)
        flag = "  <-- 上限超え" if size > limit else ""
        print(f"{name:6s} {size / 1024 / 1024:7.1f} MB{flag}")
        if size > limit:
            sys.exit(1)

    print("\nタグは依存の順に打つ:")
    print(" ".join([f"base/{version}"] + [f"{p}/{version}" for p in ps] + [version]))


if __name__ == "__main__":
    main()
