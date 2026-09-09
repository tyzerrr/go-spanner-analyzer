#!/usr/bin/env python3
"""wasm-build のキャッシュから、指定した出力（.o / .a）の項目と実体を取り除く。

使い方: python3 tools/invalidate_wasm_cache.py <出力パスの末尾> [...]
例:     python3 tools/invalidate_wasm_cache.py /obj/facade.o /libfacade.a

wasmify の wasm-build はコンパイル手順を args_hash（コマンド引数のハッシュ）だけで
キャッシュし、ソースの中身を見ない。ソースを書き換えても引数が同じなら古い .o を
使い回し、リンク結果で新しい関数が未解決の import になる（症状: env import が増え、
その名前が自分の関数）。全部作り直す --no-cache は数時間かかるので、変えたソースの
出力だけをここで消してから make wasm を回す。
"""
import json
import os
import sys

CACHE = ".wasmify/wasm-build/build-cache.json"


def main():
    suffixes = sys.argv[1:]
    if not suffixes:
        sys.exit(__doc__)
    if not os.path.exists(CACHE):
        sys.exit(f"{CACHE} が無い。make wasm を一度も回していない木では不要")

    d = json.load(open(CACHE))
    removed = []
    for key in list(d["entries"]):
        out = d["entries"][key]["output_file"]
        if not any(out.endswith(s) for s in suffixes):
            continue
        del d["entries"][key]
        removed.append(key)
        # 項目は /work/... （コンテナ内）で記録されている。ホスト側の実体を消す
        host = out.replace("/work/", os.getcwd() + "/", 1)
        if os.path.exists(host):
            os.remove(host)
            print("deleted", host)
    json.dump(d, open(CACHE, "w"), indent=2)
    print(f"removed {len(removed)} cache entries")
    for k in removed:
        print(" ", k)
    if not removed:
        sys.exit("一致する項目が無い。末尾の指定を確認")


if __name__ == "__main__":
    main()
