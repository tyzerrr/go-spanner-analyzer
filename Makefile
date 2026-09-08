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

.PHONY: arch classify build headers bridge proto wasm go all shell

arch:     ; $(DOCKER) bash -c 'wasmify save-arch < arch.json'
classify: ; $(DOCKER) wasmify classify --target $(TARGET)
build:    ; $(DOCKER) bash -c 'wasmify build --non-interactive && wasmify generate-build' && python3 tools/fix_build_json.py build.json
headers:  ; $(DOCKER) bash -c 'wasmify validate-build && wasmify parse-headers'
bridge:   ; python3 tools/set_bridge.py $(STAGE)
proto:    ; $(DOCKER) wasmify gen-proto --package $(PACKAGE)
wasm:     ; $(DOCKER) wasmify wasm-build --optimize --non-interactive --no-cache
go:       ; $(DOCKER) buf generate
# wasm2go はメモリを食うのでホストで生成する（Docker 内では OOM になった）
go-host:  ; mkdir -p build/proto-host && cp -R proto/. build/proto-host/ && cp tools/proto-buf.yaml build/proto-host/buf.yaml && tools/gen_go_host.sh build/proto-host .wasmify/wasm-build/output/spanner_emulator.wasm build/wasm2go-host
all: arch classify build headers bridge proto wasm go
shell:    ; $(DOCKER) bash
