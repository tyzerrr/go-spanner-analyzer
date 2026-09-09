package spanneranalyzer

import "testing"

// 段階 3（クエリの意味解析）。スキーマは DDL から組み立て、その上でクエリと DML の
// 名前解決と型検査を行う。位置は文中の 1 始まりの行・列で返る。
func TestAnalyzeQuery(t *testing.T) {
	if err := Init(); err != nil {
		t.Fatal(err)
	}
	schema := []string{
		"CREATE TABLE Singers (SingerId INT64 NOT NULL, Name STRING(MAX), Age INT64) PRIMARY KEY (SingerId)",
		"CREATE TABLE Albums (SingerId INT64 NOT NULL, AlbumId INT64 NOT NULL, Title STRING(MAX)) PRIMARY KEY (SingerId, AlbumId), INTERLEAVE IN PARENT Singers ON DELETE CASCADE",
	}

	valid := []string{
		"SELECT SingerId, Name FROM Singers WHERE SingerId = 1",
		"SELECT s.Name, a.Title FROM Singers AS s JOIN Albums AS a ON s.SingerId = a.SingerId",
		"SELECT COUNT(*) FROM Albums WHERE Title LIKE 'A%'",
		"INSERT INTO Singers (SingerId, Name) VALUES (1, 'x')",
		"UPDATE Singers SET Age = Age + 1 WHERE SingerId = @id",
		"DELETE FROM Albums WHERE AlbumId = 3",
	}
	for _, sql := range valid {
		errs, err := AnalyzeQuery(schema, sql)
		if err != nil {
			t.Fatalf("%s: %v", sql, err)
		}
		if len(errs) != 0 {
			t.Errorf("valid statement rejected: %s\n  %+v", sql, *errs[0])
		}
	}

	cases := []struct {
		name, sql, want string
		line, column   int32
	}{
		{"存在しないテーブル", "SELECT 1 FROM NoSuchTable", "not found", 1, 15},
		{"存在しない列", "SELECT NoSuchColumn FROM Singers", "Unrecognized name: NoSuchColumn", 1, 8},
		{"型の不一致", "SELECT * FROM Singers WHERE Name = 1", "No matching signature", 1, 29},
		{"2行目の誤り", "SELECT SingerId\nFROM Singerz", "not found", 2, 6},
		{"DML の存在しない列", "UPDATE Singers SET NoSuchColumn = 1 WHERE SingerId = 1", "NoSuchColumn", 1, 20},
	}
	for _, c := range cases {
		errs, err := AnalyzeQuery(schema, c.sql)
		if err != nil {
			t.Fatalf("%s: %v", c.name, err)
		}
		if len(errs) == 0 {
			t.Errorf("%s: expected an error", c.name)
			continue
		}
		e := errs[0]
		t.Logf("%s: line=%d col=%d %s", c.name, e.Line, e.Column, e.Message)
		if !contains(e.Message, c.want) {
			t.Errorf("%s: message %q does not contain %q", c.name, e.Message, c.want)
		}
		if e.Line != c.line || e.Column != c.column {
			t.Errorf("%s: position = %d:%d, want %d:%d", c.name, e.Line, e.Column, c.line, c.column)
		}
		if e.StatementIndex != -1 {
			t.Errorf("%s: statement_index = %d, want -1", c.name, e.StatementIndex)
		}
	}

	// スキーマ側が壊れていれば、その誤りが返り、クエリは見ない。
	errs, err := AnalyzeQuery([]string{"CREATE TABLE X (A INT64) PRIMARY KEY (NoSuchCol)"}, "SELECT 1")
	if err != nil {
		t.Fatal(err)
	}
	if len(errs) == 0 || !contains(errs[0].Message, "nonexistent key column NoSuchCol") {
		t.Errorf("broken schema: got %+v, want the DDL error", errs)
	}
}
