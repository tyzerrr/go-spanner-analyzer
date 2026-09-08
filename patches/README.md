# 上流（cloud-spanner-emulator）への変更

サブモジュールは上流のコミットに固定し、変更はここのパッチとして持つ。
適用: `cd cloud-spanner-emulator && git apply ../patches/*.patch`

| パッチ | 内容 |
|---|---|
| `0001-remove-postgresql-dialect.patch` | PostgreSQL 方言の実装（`third_party/spanner_pg`、158 万行）への依存を、`//backend/schema/updater:schema_updater` の推移的依存から外す。PostgreSQL 方言の経路は `absl::UnimplementedError` を返す。GoogleSQL 方言でも `PG.*` 関数と `PG.NUMERIC` `PG.JSONB` 型は使えなくなる |
| `0002-add-facade.patch` | `backend/schema/facade/` を追加。wasmify で公開する平易な型だけの API（`ParseDDL` 構文のみ、`ValidateDDL` 意味まで） |

変更したファイルには Apache-2.0 4(b) に従い `MODIFIED by go-spanner-analyzer` の注記を入れている。
`0001-deps-walk-after.txt` は `tools/bazel_deps_walk.py` の出力で、適用後に `spanner_pg` へ到達しないことの記録。
