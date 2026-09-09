# 上流（cloud-spanner-emulator）への変更

サブモジュールは上流のコミットに固定し、変更はここのパッチとして持つ。
適用: `cd cloud-spanner-emulator && git apply ../patches/*.patch`

| パッチ | 内容 |
|---|---|
| `0001-remove-postgresql-dialect.patch` | (1) PostgreSQL 方言の実装（`third_party/spanner_pg`、158 万行）への依存を `//backend/schema/facade` の推移的依存から外す。PostgreSQL 方言の経路は `absl::UnimplementedError` を返す。GoogleSQL 方言でも `PG.*` 関数と `PG.NUMERIC` `PG.JSONB` 型は使えなくなる。(2) gRPC と google-cloud-cpp への依存も外す（first-party のコードは使っておらず、BUILD の宣言だけだった。wasi では動かない）。(3) それらのヘッダ経由で間接的に入っていた `google/spanner/v1/type.pb.h` を 2 ファイルで直接 include |
| `0002-add-facade.patch` | `backend/schema/facade/` を追加。wasmify で公開する平易な型だけの API（`ParseDDL` 構文のみ、`ValidateDDL` DDL の意味まで、`AnalyzeQuery` クエリ・DML の名前解決と型検査）。`AnalyzeQuery` はエミュレータの `backend/query/catalog_test.cc` と同じ経路で、エラー位置は `ErrorLocation` の payload から 1 始まりの行・列として取り出す |

変更したファイルには Apache-2.0 4(b) に従い `MODIFIED by go-spanner-analyzer` の注記を入れている。
`0001-deps-walk-after.txt` は `tools/bazel_deps_walk.py` の出力で、適用後に `spanner_pg` へ到達しないことの記録。
