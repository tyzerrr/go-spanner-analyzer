# 進捗記録

夜間作業のログ。新しいものが上。

## 2026-09-09

### 計画
- P1a: `//backend/schema/parser:ddl_parser` のネイティブビルドを wasmify で記録する（Bazel が動くか、JavaCC が通るか）
- B: ファサード `backend/schema/facade/` を書く（構文のみ版 `facade_syntax`、本命版 `facade`）
- C: PostgreSQL 方言を外すパッチ（`patches/0001-remove-postgresql-dialect.patch`）
- P1b: 構文のみ版を wasm → Go まで通す
- P2/P3: パッチ適用後、本命版を wasm → Go まで通す

### 判断の記録
- Bazel のキャッシュは Docker ボリューム `go-spanner-analyzer-bazel` に置く。`--rm` のコンテナでも残る
- Bazel は同時に 1 つのコンテナからしか動かさない（出力先を共有しているため）
- 上流は `fc811a1a` (2026-09-04) に固定
- wasi-sdk の clang 22 は `.bazelrc` の `-fpermissive` `-include limits` を受け付ける（実測、対処不要）
- PostgreSQL 本体は `setjmp/longjmp` を 211 箇所使うため、wasm には持ち込まない。外す

### 経過
- 00:03 リポジトリ作成、サブモジュール追加、`wasmify init`
- 00:04 `save-arch`、`classify --target ddl_parser`
- 00:05 P1a ビルド開始（Docker メモリ 20 GB、6 CPU、Rosetta）
