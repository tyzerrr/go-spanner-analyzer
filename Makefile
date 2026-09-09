# go-spanner-analyzer: wasmify のパイプラインを Docker の中で回す。
# Bazel のキャッシュは名前付きボリュームに残す（--rm でも消えない）。
# 注意: Bazel を使う段階（build/headers）と wasm-build は同じ実行ルートを共有するので、同時に走らせない。
IMAGE    ?= ghcr.io/goccy/wasmify:edge
PLATFORM ?= linux/amd64
MEMORY   ?= 18g
CPUS     ?= 6
STAGE    ?= syntax
PACKAGE  ?= spanneranalyzer
TARGET_syntax = facade_syntax
TARGET_full   = facade
TARGET = $(TARGET_$(STAGE))

DOCKER = docker run --rm --platform $(PLATFORM) \
  -v $(CURDIR):/work -w /work \
  -v go-spanner-analyzer-bazel:/root/.cache/bazel \
  -v go-spanner-analyzer-bazelisk:/root/.cache/bazelisk \
  --memory=$(MEMORY) --cpus=$(CPUS) $(IMAGE)

.PHONY: arch classify build headers bridge proto wasm wasm-invalidate go all shell

arch:     ; $(DOCKER) bash -c 'wasmify save-arch < arch.json'
classify: ; $(DOCKER) wasmify classify --target $(TARGET)
build:    ; $(DOCKER) bash -c 'wasmify build --non-interactive && wasmify generate-build'
# fix_build_json は validate-build の後（出力が揃った後）にコンテナ内で実行する
headers:  ; $(DOCKER) bash -c 'wasmify validate-build && python3 tools/fix_build_json.py build.json && wasmify parse-headers'
bridge:   ; python3 tools/set_bridge.py $(STAGE)
proto:    ; $(DOCKER) wasmify gen-proto --package $(PACKAGE)
# wasm-build のキャッシュはコマンド引数のハッシュだけで判定し、ソースの中身を見ない。
# ソースを変えたら先に make wasm-invalidate FILES="/obj/facade.o /libfacade.a" で該当の出力を消す。
# 消し忘れると古い .o がリンクされ、新しい関数が未解決の env import になる。
# 既定はキャッシュ利用。全部作り直すときは make wasm NOCACHE=1（Rosetta 経由の直列コンパイルで数時間かかる）
wasm-invalidate: ; python3 tools/invalidate_wasm_cache.py $(FILES)
wasm:     ; $(DOCKER) wasmify wasm-build --optimize --non-interactive $(if $(NOCACHE),--no-cache,)
go:       ; $(DOCKER) buf generate
# wasm2go はメモリを食うのでホストで生成する（Docker 内では OOM になった）
go-host:  ; mkdir -p build/proto-host && cp -R proto/. build/proto-host/ && cp tools/proto-buf.yaml build/proto-host/buf.yaml && tools/gen_go_host.sh build/proto-host .wasmify/wasm-build/output/spanner_emulator.wasm build/wasm2go-host
all: arch classify build headers bridge proto wasm go
shell:    ; $(DOCKER) bash
