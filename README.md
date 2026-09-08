# go-spanner-analyzer

Spanner エミュレータの DDL 検証部分を純 Go のライブラリにしたもの（作業中）。

エミュレータ（C++）を wasmify で wasm32-wasip1 にビルドし、wasm2go で Go に変換する。
cgo も外部プロセスも不要で、`go install` だけで Spanner 本物と同じ DDL の意味検証ができることを目指す。

| 段階 | 公開する関数 | 状態 |
|---|---|---|
| 1 | `ParseDDL(ddls []string)` 構文のみ | **動作確認済み**（wazero 版、wasm2go 版 amd64/arm64。linux/windows/darwin へクロスコンパイル可） |
| 2 | `ValidateDDL(ddls []string)` 意味まで（主キー・INTERLEAVE・索引・外部キー…） | 作業中 |
| 3 | `AnalyzeQuery(sql string)` クエリの意味解析 | 未着手 |

Day1 は GoogleSQL 方言のみ。PostgreSQL 方言はビルドから外している（`patches/`）。

## 構成

```
cloud-spanner-emulator/   上流（git submodule、コミット固定）
patches/                  上流への変更（PostgreSQL 除去、ファサード追加）
wasmify.json arch.json    wasmify の設定
buf.yaml buf.gen.yaml     Go 生成の設定
tools/                    補助スクリプト
build/                    生成物（git 管理外）
```

## ライセンス

Apache-2.0。上流の帰属表示は `NOTICE` と `THIRD_PARTY_NOTICES.txt` を参照。
Spanner は Google LLC の商標。本プロジェクトは Google と無関係。
