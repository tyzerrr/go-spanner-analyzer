#!/usr/bin/env bash
# wasm から Go を生成する（ホストで実行）。
# Docker 内の protoc-gen-wasmify-go は wasm2go の段階でメモリ不足になりやすいので、
# プラグインをホストでビルドして使う。buf はホストに入っていること。
#
# 使い方: tools/gen_go_host.sh <proto dir> <wasm> <out dir>
set -euo pipefail
PROTO_DIR=${1:?proto dir}; WASM=${2:?wasm path}; OUT=${3:?out dir}
ROOT=$(cd "$(dirname "$0")/.." && pwd)
BIN=$ROOT/build/bin
WASMIFY_REPO=${WASMIFY_REPO:-https://github.com/goccy/wasmify.git}
WASMIFY_REV=${WASMIFY_REV:-85d7c58}   # 動作確認した版
mkdir -p "$BIN"
if [ ! -x "$BIN/protoc-gen-wasmify-go" ]; then
  echo "==> protoc-gen-wasmify-go をビルド ($WASMIFY_REV)"
  tmp=$(mktemp -d); git clone -q "$WASMIFY_REPO" "$tmp/wasmify"; git -C "$tmp/wasmify" checkout -q "$WASMIFY_REV"
  (cd "$tmp/wasmify" && go build -o "$BIN/protoc-gen-wasmify-go" ./protoc-plugins/protoc-gen-wasmify-go)
  rm -rf "$tmp"
fi
WASM_ABS=$(cd "$(dirname "$WASM")" && pwd)/$(basename "$WASM")
OUT_ABS=$(mkdir -p "$OUT" && cd "$OUT" && pwd)
TEMPLATE=$PROTO_DIR/buf.gen.wasm2go.yaml   # 拡張子が無いと buf がインライン JSON と解釈して失敗する
cat > "$TEMPLATE" <<YAML
version: v2
inputs:
  - directory: .
plugins:
  - local: protoc-gen-wasmify-go
    out: $OUT_ABS
    opt:
      - module=github.com/tyzerrr/go-spanner-analyzer
      - runtime=wasm2go
      - wasm=$WASM_ABS
YAML
echo "==> buf generate (wasm2go) -> $OUT_ABS"
( cd "$PROTO_DIR" && PATH="$BIN:$PATH" buf generate --template buf.gen.wasm2go.yaml )
rm -f "$TEMPLATE"
# Go モジュールとして動く形に整える（開発用の replace 付き）
cp "$ROOT/tests/go/go.mod.txt" "$OUT_ABS/go.mod"
cp "$ROOT/tests/go/go.mod.wasm2go-internal.txt" "$OUT_ABS/internal/wasm2go/go.mod"
echo "==> done: $OUT_ABS"
