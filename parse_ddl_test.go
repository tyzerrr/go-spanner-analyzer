package spanneranalyzer

import "testing"

// 段階 1（構文のみ）。生成された build/wasm2go/ にコピーして実行する。
func TestParseDDL(t *testing.T) {
	if err := Init(); err != nil {
		t.Fatal(err)
	}
	errs, err := ParseDDL([]string{
		"CREATE TABLE Singers (SingerId INT64 NOT NULL, Name STRING(MAX)) PRIMARY KEY (SingerId)",
		"CREATE TABLE Bad (Id INT64 NOT) PRIMARY KEY (Id)",
		"CREATE CHANGE STREAM S FOR Singers",
		"CREATE INDEX Idx ON Singers(Name) STORING (",
	})
	if err != nil {
		t.Fatal(err)
	}
	for _, e := range errs {
		t.Logf("stmt=%d line=%d col=%d %s", e.StatementIndex, e.Line, e.Column, e.Message)
	}
	if len(errs) != 2 {
		t.Fatalf("want 2 syntax errors, got %d", len(errs))
	}
	if errs[0].StatementIndex != 1 || errs[0].Line != 1 || errs[0].Column != 31 {
		t.Errorf("unexpected position for first error: %+v", *errs[0])
	}
}
