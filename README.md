# go-spanner-analyzer

[![Go Reference](https://pkg.go.dev/badge/github.com/tyzerrr/go-spanner-analyzer.svg)](https://pkg.go.dev/github.com/tyzerrr/go-spanner-analyzer)

Pure-Go bindings for the DDL analyzer inside
[Cloud Spanner Emulator](https://github.com/GoogleCloudPlatform/cloud-spanner-emulator).
`ParseDDL` and `ValidateDDL` produce the same diagnostics as the
emulator — including primary keys, INTERLEAVE, indexes, and foreign
keys — without cgo, a native toolchain, or a running emulator
process.

## Why this library

Cloud Spanner's schema rules live in the emulator's C++ backend.
Calling that code from Go normally means cgo, a C++ toolchain, or
shelling out to the emulator binary — all of which hurt
cross-compilation, static linking, and `go install`.

`go-spanner-analyzer` compiles the emulator down to WebAssembly
(`wasm32-wasip1`) with
[`goccy/wasmify`](https://github.com/goccy/wasmify) and then
transpiles that wasm to pure Go source via
[`goccy/wasm2go`](https://github.com/goccy/wasm2go) — no cgo, no
native toolchain, no embedded wasm runtime, just a regular Go
library.

## Features

- **Pure Go, no cgo, no wasm runtime.** The emulator is transpiled
  from WebAssembly directly to Go source by
  [`goccy/wasm2go`](https://github.com/goccy/wasm2go), so there is
  no embedded interpreter or JIT — the engine is just Go code the
  toolchain compiles ahead of time. `CGO_ENABLED=0` builds, static
  linking, and cross-compilation all work without extra setup.
- **Same diagnostics as the emulator.** `ValidateDDL` applies
  statements in order to an empty schema the way the emulator does
  for `CreateDatabase`. Missing parent tables, ARRAY primary keys,
  unknown key columns, unknown index columns, and duplicate names
  come back with the emulator's own wording.
- **Auto-generated bridge.** The Go API in `spanneranalyzer.go` is
  produced by [`goccy/wasmify`](https://github.com/goccy/wasmify).
  The transpiled engine lives in
  [`tyzerrr/spanneranalyzerwasm2go`](https://github.com/tyzerrr/spanneranalyzerwasm2go).
- **GoogleSQL dialect (Day 1).** PostgreSQL dialect and gRPC are
  stripped from the build (`patches/`). ICU is linked for
  case-insensitive comparison and normalization only.

## Status

Tracks Cloud Spanner Emulator
[`fc811a1a`](https://github.com/GoogleCloudPlatform/cloud-spanner-emulator/commit/fc811a1a93c7e4784db7f48fe15e72fe94f39d38)
(2026-09-04).

| API | What it does | Status |
|---|---|---|
| `ParseDDL(ddls []string)` | Syntax only | Available (amd64/arm64; linux/windows/darwin) |
| `ValidateDDL(ddls []string)` | Semantics (keys, INTERLEAVE, indexes, FKs, …) | Available |
| `AnalyzeQuery(ddls []string, sql string)` | Query and DML semantics: names resolved against the schema the DDL describes, and the statement type-checked. Errors carry a 1-based line and column within the statement | **Working** (v0.2.0) |

The public API is still settling.

## Installation

```sh
go get github.com/tyzerrr/go-spanner-analyzer
```

While the repositories are private, set
`GOPRIVATE=github.com/tyzerrr/*` so the Go toolchain can fetch
them.

The first build is heavy: the engine is shipped as transpiled Go
source (~750 MB across
[`spanneranalyzerwasm2go`](https://github.com/tyzerrr/spanneranalyzerwasm2go)).
Go modules are capped at 500 MiB, so that tree is split into 14
nested modules (root, `base`, `p0`–`p11`). Expect a cold build to
take tens of seconds. See
[Resource footprint](#resource-footprint) for measured numbers.

## Synopsis

### Initialize the engine

`Init` initializes the transpiled wasm2go engine. Call it once per
process before using any other API; it is `sync.Once`-guarded so
calling more than once is a no-op. There is no runtime to tear
down, so no `Close` is needed.

```go
package main

import "github.com/tyzerrr/go-spanner-analyzer"

func main() {
    if err := spanneranalyzer.Init(); err != nil {
        panic(err)
    }

    // ...use ParseDDL / ValidateDDL here...
}
```

### Parse DDL (syntax only)

`ParseDDL` checks each statement independently with the
emulator's DDL parser. It does not look at schema semantics, and
it returns every syntax error it finds.

```go
errs, err := spanneranalyzer.ParseDDL([]string{
    "CREATE TABLE Singers (SingerId INT64 NOT NULL, Name STRING(MAX)) PRIMARY KEY (SingerId)",
    "CREATE TABLE Bad (Id INT64 NOT) PRIMARY KEY (Id)",
})
if err != nil {
    panic(err)
}
for _, e := range errs {
    fmt.Printf("stmt=%d line=%d col=%d %s\n",
        e.StatementIndex, e.Line, e.Column, e.Message)
}
```

### Validate DDL (semantics)

`ValidateDDL` applies the statements in order to an empty schema,
the way the emulator does for `CreateDatabase`. It stops at the
first semantic error. An empty slice means the DDL is valid.

```go
errs, err := spanneranalyzer.ValidateDDL([]string{
    "CREATE TABLE Singers (SingerId INT64 NOT NULL, Name STRING(MAX)) PRIMARY KEY (SingerId)",
    "CREATE INDEX Bad ON Singers(NoSuchColumn)",
})
if err != nil {
    panic(err)
}
// errs[0].Message == "Index Bad specifies key column NoSuchColumn which does not exist in the index's base table."
```

## Resource footprint

Because the emulator ships as ahead-of-time transpiled Go (in
`spanneranalyzerwasm2go`) instead of a wasm module plus a
runtime, the cost shifts from process startup to the Go
toolchain: compilation is heavier than a typical dependency, but
in exchange `spanneranalyzer.Init` is cheap and `ValidateDDL`
itself is effectively instantaneous.

Approximate numbers from a clean consumer module (2026-09-09):

| Phase | Wall time |
|---|---|
| `go get` (14 nested modules) | ~15 s |
| First `CGO_ENABLED=0` build | ~32 s |

The generated engine is ~750 MB of source (~39.5 million lines)
across the nested modules. Subsequent builds with a warm cache
complete in a few seconds.

## License

[Apache-2.0](LICENSE). Upstream attribution is in
[NOTICE](NOTICE) and
[THIRD_PARTY_NOTICES.txt](THIRD_PARTY_NOTICES.txt).

Spanner is a trademark of Google LLC. This project is not
affiliated with or endorsed by Google.
