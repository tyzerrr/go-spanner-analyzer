WASMIFY := wasmify
# Path to the upstream C/C++ project. Override on CI if your layout differs:
#   make wasm PROJECT=./path/to/upstream
PROJECT ?= ./cloud-spanner-emulator
OUTPUT_DIR := .

.PHONY: all update wasm tools clean

# Install tools listed in arch.json (cmake, bazel, ...) plus wasi-sdk. Safe to
# re-run; already-installed tools are skipped.
tools:
	$(WASMIFY) ensure-tools $(PROJECT) --output-dir $(OUTPUT_DIR)

# Upstream changes: detect and re-run only the affected phases.
update:
	$(WASMIFY) update $(PROJECT) --output-dir $(OUTPUT_DIR)

# Build wasm binary. Depends on tools so CI runners do not need any
# pre-installed build dependencies beyond wasmify itself. --optimize
# chains a binaryen wasm-opt pass after the link.
wasm: tools
	$(WASMIFY) wasm-build --optimize --non-interactive --output-dir $(OUTPUT_DIR)

all: update wasm

clean:
	rm -rf wasm/*.wasm
