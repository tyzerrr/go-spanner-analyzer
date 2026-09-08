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
- 00:15 ファサードを書いた: `cloud-spanner-emulator/backend/schema/facade/`（`types.h` `syntax.{h,cc}`=ParseDDL 構文のみ、`facade.{h,cc}`=ValidateDDL 意味まで、`BUILD`）。上流の `tests/common/schema_constructor.cc` と同じ呼び方。サブモジュール内の新規ファイルなので、後でパッチ `0002-add-facade` として切り出す
- 00:18 `arch.json` に `facade_syntax` `facade` の 2 的を追加。`tools/set_bridge.py`（bridge/skip 節の書き込み）、`buf.yaml`、`buf.gen.yaml` を用意。`save-arch` は P1a 完了後に実行（実行中の `wasmify build` と状態ファイルが競合するため）
- 00:10 PostgreSQL 除去パッチの草案を補助エージェントに依頼（対象: schema_updater / validators / datamodel:types / query:catalog / query:function_catalog と各 BUILD。成果物は `patches/0001-remove-postgresql-dialect.patch`）
- 00:21 **P1a 成功**。`ddl_parser` のネイティブビルドを 16 分で記録（1,351 手順: compile 760 / link 197 / archive 394、コンパイラは gcc）。JavaCC の生成物（`DDLParser.cc` `ParseException.cc` `DDLParserTokenManager.cc`）が JDK 経由で作られてコンパイルされた。Bazel・JDK・JavaCC はコンテナ内で動く
- 00:22 P1b 開始: `save-arch` → `classify --target facade_syntax` → 記録 → `parse-headers` → bridge（`ParseDDL` のみ公開）→ `gen-proto` → `wasm-build` → `buf generate` を一続きで実行中
