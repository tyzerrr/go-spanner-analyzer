// Package spanneranalyzer は、Cloud Spanner Emulator の DDL 検証を純 Go（cgo なし）で提供する。
//
// エミュレータ（C++）を wasm32-wasip1 にビルドし、wasm2go で Go に変換したものを
// github.com/tyzerrr/spanneranalyzerwasm2go として依存に持つ。外部プロセスも wasm 実行環境も要らない。
//
//	if err := spanneranalyzer.Init(); err != nil { ... }
//	errs, err := spanneranalyzer.ValidateDDL([]string{
//	    "CREATE TABLE Singers (SingerId INT64 NOT NULL, Name STRING(MAX)) PRIMARY KEY (SingerId)",
//	    "CREATE TABLE Albums (SingerId INT64 NOT NULL, AlbumId INT64 NOT NULL) PRIMARY KEY (SingerId, AlbumId), INTERLEAVE IN PARENT Singers",
//	})
//	for _, e := range errs { fmt.Println(e.Message) }
//
// 対応: GoogleSQL 方言のみ。PostgreSQL 方言は非対応。ICU のデータは正規化と照合の基本（大文字小文字を
// 同一視する比較）に絞ってある。
package spanneranalyzer
