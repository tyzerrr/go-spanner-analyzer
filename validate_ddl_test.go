package spanneranalyzer

import "testing"

// 段階 2（意味まで）。エミュレータで実測した誤りと同じものが出るはず。
func TestValidateDDL(t *testing.T) {
	if err := Init(); err != nil {
		t.Fatal(err)
	}
	ok := []string{
		"CREATE TABLE Singers (SingerId INT64 NOT NULL, Name STRING(MAX)) PRIMARY KEY (SingerId)",
		"CREATE TABLE Albums (SingerId INT64 NOT NULL, AlbumId INT64 NOT NULL) PRIMARY KEY (SingerId, AlbumId), INTERLEAVE IN PARENT Singers ON DELETE CASCADE",
		"CREATE INDEX AlbumsByAlbumId ON Albums(AlbumId)",
	}
	errs, err := ValidateDDL(ok)
	if err != nil {
		t.Fatal(err)
	}
	if len(errs) != 0 {
		t.Fatalf("valid DDL rejected: %+v", *errs[0])
	}

	cases := []struct{ name, ddl, want string }{
		{"親テーブルが無い", "CREATE TABLE X (A INT64) PRIMARY KEY (A), INTERLEAVE IN PARENT NoSuchTable", "Table not found: NoSuchTable"},
		{"主キーに ARRAY", "CREATE TABLE Y (A ARRAY<INT64>) PRIMARY KEY (A)", "has type ARRAY, but is part of the primary key"},
		{"主キーに無い列", "CREATE TABLE Z (A INT64) PRIMARY KEY (NoSuchCol)", "references nonexistent key column NoSuchCol"},
		{"索引に無い列", "CREATE INDEX Bad ON Singers(NoSuchColumn)", "which does not exist in the index's base table"},
		{"テーブル名の重複", "CREATE TABLE Singers (X INT64) PRIMARY KEY (X)", "Duplicate name in schema: Singers"},
	}
	for _, c := range cases {
		errs, err := ValidateDDL(append(append([]string{}, ok...), c.ddl))
		if err != nil {
			t.Fatalf("%s: %v", c.name, err)
		}
		if len(errs) == 0 {
			t.Errorf("%s: expected an error", c.name)
			continue
		}
		t.Logf("%s: %s", c.name, errs[0].Message)
		if !contains(errs[0].Message, c.want) {
			t.Errorf("%s: got %q, want substring %q", c.name, errs[0].Message, c.want)
		}
	}
}

func contains(s, sub string) bool {
	return len(sub) == 0 || (len(s) >= len(sub) && indexOf(s, sub) >= 0)
}

func indexOf(s, sub string) int {
	for i := 0; i+len(sub) <= len(s); i++ {
		if s[i:i+len(sub)] == sub {
			return i
		}
	}
	return -1
}
