# go-spanner-analyzer

Spanner エミュレータの DDL 検証部分を純 Go のライブラリにしたもの（2026-09-09 時点で `ParseDDL` / `ValidateDDL` が動作。公開の形は整備中）。

エミュレータ（C++）を wasmify で wasm32-wasip1 にビルドし、wasm2go で Go に変換する。
cgo も外部プロセスも不要で、`go install` だけで Spanner 本物と同じ DDL の意味検証ができることを目指す。

| 段階 | 公開する関数 | 状態 |
|---|---|---|
| 1 | `ParseDDL(ddls []string)` 構文のみ | **動作確認済み**（wazero 版、wasm2go 版 amd64/arm64。linux/windows/darwin へクロスコンパイル可） |
| 2 | `ValidateDDL(ddls []string)` 意味まで（主キー・INTERLEAVE・索引・外部キー…） | **動作確認済み**（wazero 版と純 Go 版の両方。親テーブル無し・主キーに ARRAY・主キーに無い列・索引に無い列・重複を本物と同じ文言で検出） |
| 3 | `AnalyzeQuery(sql string)` クエリの意味解析 | 未着手 |

Day1 は GoogleSQL 方言のみ。PostgreSQL 方言と gRPC はビルドから外している（`patches/`）。ICU は wasm 向けに自前ビルドしてリンクしている（`tools/build_icu_wasm.sh`）。

## 使い方

```go
import "github.com/tyzerrr/go-spanner-analyzer"

func main() {
    if err := spanneranalyzer.Init(); err != nil { panic(err) }
    errs, err := spanneranalyzer.ValidateDDL([]string{
        "CREATE TABLE Singers (SingerId INT64 NOT NULL, Name STRING(MAX)) PRIMARY KEY (SingerId)",
        "CREATE INDEX Bad ON Singers(NoSuchColumn)",
    })
    // errs[0].Message == "Index Bad specifies key column NoSuchColumn which does not exist in the index's base table."
}
```

`go get github.com/tyzerrr/go-spanner-analyzer` で入る。純 Go の本体（約 750 MB のソース）は
`github.com/tyzerrr/spanneranalyzerwasm2go` から取得される。Go のモジュールは 1 つ 500 MiB までなので、
本体は 14 個の入れ子モジュール（root、`base`、`p0`〜`p11`）に分かれている。初回のビルドだけ数十秒かかる。
どちらも非公開リポジトリのあいだは `GOPRIVATE=github.com/tyzerrr/*` が要る。

## 構成

```
spanneranalyzer.go        Go の API（wasmify が生成した呼び出し口）
go.mod                    spanneranalyzerwasm2go に依存
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
