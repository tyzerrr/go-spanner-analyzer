# wasm2go v0.5.15: import path にハイフンがあると arm64 アセンブリが壊れる

上流（goccy/wasm2go）への報告用の記録。2026-09-09。

## 症状

`Wasm2GoImportPath`（proto の `wasmify.wasm2go_package`）にハイフンを含むパスを指定すると、
生成される `arm64.s` の多数のオペランドに、パスの「最後のハイフンまで」の文字列が割り込む。
amd64.s は無傷。`go build` は `expected '(', found .` で失敗する。

```
MOVD  R0, github.com/tyzerrr/go-spanner-m+0(FP)      # 正: MOVD R0, m+0(FP)
MOVW  R6, github.com/tyzerrr/go-spanner-84(RSP)      # 正: MOVW R6, 84(RSP)
MOVW  R1, github.com/tyzerrr/go-spanner-l0+8(FP)     # 正: MOVW R1, l0+8(FP)
```

## 切り分け（wasmify の玩具プロジェクト minischema、200 KB の wasm、protoc-gen-wasmify-go を wasmify main から build）

| wasm2go の import path | ハイフン | モジュール配下 | arm64.s 混入行 | amd64.s 混入行 |
|---|---|---|---|---|
| `github.com/example/go-mini-schema-w2g` | あり | いいえ | 30,990 | 0 |
| `github.com/example/go-minischema/internal/wasm2go` | あり | はい | 30,990 | 0 |
| `github.com/example/gominischema/internal/wasm2go` | なし | はい | 0 | 0 |
| `github.com/example/gominischemaw2g` | なし | いいえ | 0 | 0 |

ハイフンの有無だけで決まる。

## 手掛かり

- `internal/asmgen/plan9path.go` の `Plan9AsmPathSafe` はハイフン入りのパスを「Plan 9 で綴れない」と判定し、
  `internal/gcasm/bundle.go` はその場合に `gcasmFwd` の Go ラッパー経由へ切り替える設計になっている
  （bundle.go 748-768 付近のコメント）。つまりハイフン入りパスは想定内のはずで、
  arm64 の出力経路のどこかでパスがオペランドに混入している
- 混入する文字列は「パスの最後のハイフンまで」（`go-spanner-analyzer` → `go-spanner-`）

## 再現手順

1. wasmify の実習プロジェクト（spnls リポジトリ `docs/handson/`）で `make wasm` 相当まで実行し `minischema.wasm` を得る
2. `proto/minischema.proto` の `option (wasmify.wasm2go_package)` をハイフン入りのパスに書き換える
3. `buf generate`（`runtime=wasm2go`）→ `internal/wasm2go/arm64.s` に混入行が出る（`grep -c 'github.com/example/' arm64.s`）
4. 同じ手順でハイフン無しのパスにすると 0 行
