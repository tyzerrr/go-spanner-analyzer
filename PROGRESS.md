# 進捗記録

## 朝のまとめ（2026-09-09 08:10 時点）

**結論: エミュレータの DDL 意味検証を、cgo も外部プロセスも無しの純 Go として動かせた。**

| 段階 | 状態 |
|---|---|
| 構文のみ `ParseDDL` | 完了。wazero 版 / 純 Go 版（amd64・arm64）で動作。他 OS へクロスコンパイル可 |
| 意味まで `ValidateDDL` | **完了。** wazero 版 / 純 Go 版（arm64）で動作。5 種の意味エラーを本物と同じ文言で検出 |
| クエリ `AnalyzeQuery` | 未着手（第 3 段階） |

数字: 本命 wasm 14.8 MB → 純 Go 720 MB（3,800 万行）。wasm2go 変換 7 分・13.3 GB（ホストで実行）。テストはビルド込み 21 秒、`ValidateDDL` 自体は瞬時。

やったこと（詳細は下の時系列）:
1. `patches/0001`: PostgreSQL 方言・gRPC・google-cloud-cpp を依存から外す（44 ファイル）。コンパイル対象が 8,860 → 1,823 手順に
2. `patches/0002`: ファサード `backend/schema/facade/`（`ParseDDL` `ValidateDDL`）
3. wasmify の落とし穴を 3 つ道具で回避: GCC 専用フラグ（`tools/fix_build_json.py`）、差分ビルドでの誤 skip（同上、`validate-build` の後に実行）、wasm2go の import path はモジュール外にする（`tools/set_bridge.py`）
4. wasm2go は Docker 内で OOM するのでホストで実行（`tools/gen_go_host.sh`、`make go-host`）

残っている課題:
- ~~ICU が wasm にリンクされていない~~ → **解決**（09:00 台）。ICU 76.1 を wasm 向けに自前ビルドし `prebuilt_archives` でリンク。外部参照 87 → 45（ICU 由来 0）。残りは absl のログ関連と例外の受け口
- 公開の形: 生成物（720 MB）をどう配布するか。googlesql-wasm 同様、変換物は別モジュール `github.com/tyzerrr/spanneranalyzerwasm2go` として出す前提で `replace` を使っている
- `facade` の BUILD 依存に不足がある可能性（cc_library は未定義シンボルを検出しない）
- wasm2go の arm64 不具合（**import path にハイフンがあると壊れる**。当初「モジュール配下だから」と考えたのは誤りで、玩具で切り分けて訂正）は上流に報告する（`docs/wasm2go-arm64-hyphen.md`）
- 手順の再現性: 今回は手作業が多かった。`Makefile` と `tools/` に集約したが、通しで再実行して確かめる

再現の最短経路（ホスト）: `make classify STAGE=full && make build && make headers` の後に `python3 tools/fix_build_json.py`（コンテナ内、`validate-build` 後）→ `make bridge STAGE=full proto wasm` → `make go-host` → `build/wasm2go-host` で `go test`

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
- 00:35 **PostgreSQL 除去パッチの草案完成**（`patches/0001-remove-postgresql-dialect.patch`、29 ファイル、+135/−943）。`tools/bazel_deps_walk.py` で `schema_updater` から `spanner_pg` への到達 0 件を確認。私が見積もった 5 ファイルより広く、`transaction` `actions` `query/ml` `query/search` `query/remote_udf` `schema/printer` `information_schema_catalog` も推移的に到達していた。机上確認: 変更ファイルに PG の識別子は残っていない（コメントと `"PG_CATALOG"` 文字列を除く）。**未コンパイル**。P1b 完了後に `//backend/schema/facade:facade` のネイティブビルドで検証する
- 00:36 ファサードを `patches/0002-add-facade.patch` として切り出し。`patches/README.md` を追加
- 00:39 P1b: `parse-headers` 成功（668 関数 / 243 クラス / 79 enum の品書き）、`gen-proto` 成功（`ParseDDL` 1 本、`ValidationError`）。`wasm-build` は `-fno-canonical-system-headers`（GCC 専用、Bazel の gcc ツールチェーンが付与）を wasi clang が拒否して失敗
- 00:45 対処: `tools/fix_build_json.py` で `build.json` からそのフラグを除く（762 手順）。wasmify 側に除去設定は無い（`extra_cxxflags` で足すことしかできない）。Makefile の `build` に組み込み。`wasm-build` を再開（`--memory=5g --cpus=3`、ネイティブビルドと並走）
- 00:41 P2 検証開始: パッチ適用済みの木で `bazel build //backend/schema/facade:facade //backend/schema/facade:syntax` をネイティブ実行中（wasmify を通さない素の Bazel。`bazel query` で `spanner_pg` が推移的依存に無いことも同時に確認）
- 判断: wasmify は `-mllvm -wasm-enable-sjlj` を付けている（setjmp/longjmp の wasm 対応）。PostgreSQL を入れない方針は変えないが、将来 PG 方言を足す余地はある
- 00:48 `wasm-build` 2 回目の失敗: 作業ディレクトリが Bazel の実行ルート（`/root/.cache/bazel/.../execroot/_main`）なので、`wasm-build` のコンテナにも Bazel のボリュームを付ける必要がある。付けて再開（Makefile の `DOCKER` は最初から付けてあるので、手で起動したときだけの見落とし）
- 00:49 **P2 の第一関門を通過**: `bazel query "deps(//backend/schema/facade:facade)"` で `third_party/spanner_pg` のラベルが 0 件。パッチ 0001 は Bazel の依存解決の上でも PostgreSQL を切り離せている。ネイティブビルド（`facade` と `syntax`）を実行中
- 00:52 `wasm-build` 3 回目の失敗の原因: `build.json` の 1,014/1,356 手順が `wasm_skip`（理由 "transient probe artifact: output deleted by the captured build"）。差分ビルドで作り直されなかった出力を、wasmify が「作られなかった」と誤判定した。wasm は 130 KB しかなく、生成 Go に空スタブが 187 個
- 00:53 対処: `tools/fix_build_json.py` に「出力が実在する手順の `wasm_skip` を外す」処理を追加（コンテナ内、Bazel の実行ルートが見える場所で実行する必要がある）。`wasm-build --no-cache` を再開
- 教訓: wasmify の記録は差分ビルドと相性が悪い。`wasmify build` の前に `bazel clean` するか、この道具で直す。Makefile では後者
- 00:56 修正版の `fix_build_json` が効いた: `unskipped=1014, remaining skip=0/1356`。`wasm-build` が 762 手順の本コンパイルを開始（P1b の本番）
- 00:47 **P2 ネイティブビルド 1 回目**: 6 分 24 秒、1,124 手順。失敗は 1 箇所だけ。`backend/query/remote_udf/remote_udf_evaluator.cc:67` で `google::spanner::v1::TypeAnnotationCode` が見つからない（`google/spanner/v1/type.pb.h` が消した PostgreSQL のヘッダ経由で間接的に入っていた）。パッチ 0001 の他の 28 ファイルはコンパイルを通過
- 00:57 対処: 直接 include と `@com_google_googleapis//google/spanner/v1:spanner_cc_proto` の依存を追加（MODIFIED 注記付き）。再ビルド中
- 01:00 `wasm-build` 4 回目は 48 手順目（`common/errors.cc`）で `googlesql/base/status_macros.h` が見つからず失敗。ヘッダは実在し include 指定も正しい。原因は**競合**: 同時に走らせた本命版の Bazel 再ビルドが、開始時に実行ルートの `external/*` のシンボリックリンクを作り直し、その瞬間に `wasm-build` の include が辿れなくなった（リンクの作成時刻 15:49 と失敗時刻 15:48 が一致）
- 判断: **Bazel のビルドと `wasm-build` は同じ実行ルートを共有するので同時に動かさない。** 以後は直列。`wasm-build` は本命版の再ビルド完了後に再開する（成功済みの 47 手順はキャッシュを使う）
- 01:04 P2 再ビルド 2 回目は OOM（`resolved_ast.cc` のコンパイル中に `cc1plus` が Killed）。`wasm-build` と同時実行していたための資源不足。単独で `--memory=18g --jobs=3 --local_resources=memory=12000` で 3 回目を実行中。`remote_udf_evaluator.cc` のエラーは 2 回目のログに出ていない
- 01:58 **P2 ネイティブビルド 3 回目**: 53 分、949 手順（googlesql の大半をコンパイル）。失敗は `backend/actions/change_stream.cc:71` の 1 箇所（`google::spanner::v1` 未宣言。`remote_udf` と同種）。`remote_udf_evaluator.cc` の修正は通過
- 01:59 対処: パッチで触った全ファイルを走査し、`spanner::v1` を使っていて `google/spanner/v1/*.pb.h` を直接 include していないものすべてに include と BUILD の依存を追加。4 回目を実行中（差分ビルドなので短いはず）
- 02:04 **P2 完了: パッチ適用済みの `//backend/schema/facade:facade` と `:syntax` がネイティブでビルド成功**（4 回目、4 分 18 秒、差分 32 手順）。PostgreSQL 除去パッチ（29 ファイル、+139/−943）は Bazel の依存解決と gcc のコンパイルの両方で成立。上流由来の見落としは `remote_udf_evaluator.cc` と `change_stream.cc` の 2 箇所（`google/spanner/v1/type.pb.h` の直接 include が必要）で、いずれも修正済み
- 02:05 `patches/0001` を最新化。構文版の `wasm-build` を単独で再開（Bazel と直列）
- 02:08 **P1b: 構文版の wasm が完成**（`wasm-build` 17 分、379 コンパイル + 198 archive、`spanner_emulator.wasm` 1.56 MB、外部参照は例外・ログの受け口 13 個のみ）。**wazero 版の Go で `ParseDDL` のテストが通った**: エミュレータ本物の DDL 構文解析器が Go の中で動き、`Syntax error on line 1, column 31: Expecting 'NULL' but found ')'` などを返す。生成物は `build/syntax-wazero/` に退避
- 02:15 ただし wasm2go 版は未完: run #5 の `buf generate` で `protoc-gen-wasmify-go` が **OOM で killed**（`signal: killed`、grep で終了コードが隠れていた）。`build/wasm2go` は古い 130 KB 版のままで、空スタブ 187 個はそれ由来
- 02:20 対処: wasm2go はメモリ食いなので Docker（上限 20 GB、Rosetta）ではなく **ホストの Mac（48 GB、arm64 ネイティブ）で実行**。wasmify のソースからプラグインをビルドし、`build/syntax-proto/` を入力に `build/syntax-wasm2go-host/` へ生成中
- 02:10 P3（本命版 `facade`）の wasmify パイプラインを開始（`classify` → `build` → `generate-build` → `fix_build_json` → `validate-build` → `parse-headers` → bridge(full) → `gen-proto` → `wasm-build`）。Bazel と `wasm-build` は直列
- 教訓: パイプ越しの終了コードは `PIPESTATUS` で取る。`grep -v` で握りつぶすと OOM に気づけない
- 02:17 ホストで wasm2go 生成成功（62 秒、最大 2.7 GB。Docker 内で OOM したのはコンテナ上限と Rosetta のため）。出力は `internal/wasm2go/{p0,p1}` に分割される規模。外部参照の空スタブは 13 個（wasm の実 import と一致）
- 02:19 **wasm2go 版（純 Go、`CGO_ENABLED=0`）で `ParseDDL` のテスト成功（amd64、Rosetta で実行）。** 純 Go 化の経路は端から端まで成立
- 02:19 arm64 用アセンブリだけ壊れる: `p0/arm64.s` 26 万行・`p1/arm64.s` 5.6 万行に `github.com/tyzerrr/go-spanner-N(RSP)` `...-m+N(FP)` `...-lN+N(FP)` の形でモジュールパスが混入（amd64.s は無傷）。玩具（別 import path、分割なし）では起きなかった。wasm2go v0.5.15 の arm64 出力の不具合と見ている。切り分け中: wasm2go の import path をモジュール外（`github.com/tyzerrr/spanneranalyzerwasm2go`、googlesql-wasm と同じ流儀）にして再生成
- 02:22 **arm64 の混入の原因を切り分け**: wasm2go の import path をモジュール外（`github.com/tyzerrr/spanneranalyzerwasm2go`）にして再生成すると、`p0/arm64.s` の混入が 0 行になった。モジュール配下のパスを指定したことが引き金。`tools/set_bridge.py` と `tests/go/go.mod.txt`（`replace` 付き）を修正。wasm2go 側には後で報告する
- 02:24 **第 1 段階（`ParseDDL`）完了。** arm64 ネイティブの純 Go（`CGO_ENABLED=0`）でもテスト成功（実行 0.00 秒、ビルド込み 3.4 秒）。wazero 版・wasm2go 版 amd64・wasm2go 版 arm64 のすべてで動作
- 02:26 ホストで Go を生成する手順を `tools/gen_go_host.sh` と `make go-host` に道具化（wasmify のプラグインを固定した版でビルドして使う）
- 02:30 純 Go 版（構文）のクロスコンパイル確認: linux/amd64、linux/arm64、windows/amd64、darwin/amd64 すべて OK（cgo なし、Apple Silicon の Mac 上で）。README の段階 1 を「動作確認済み」に
- 02:30 P3（本命版）は `validate-build` の途中（googlesql をネイティブで再コンパイル中）。完了後に `parse-headers` → `gen-proto`（`ValidateDDL` 追加）→ `wasm-build` と進む
- 05:10 **P3（本命版）1 回目の結果**: `wasmify build` は 8,855 手順を記録（compile 5,472）。`validate-build` に 2 時間 50 分（googlesql 等をネイティブで再コンパイル）。`parse-headers` は 799 関数 / 554 クラス。`gen-proto` は `ValidateDDL` のみ公開（`ParseDDL` は `facade` の到達ヘッダに無かった）。**`wasm-build` は 3,289 手順を skip して 0.3 MB の wasm しか作れず失敗扱い**。原因は `fix_build_json` を `validate-build` の前に実行したこと（その時点では出力が無く、5,716 手順の skip を外せなかった）
- 05:12 対処 2 点: (1) `facade.h` が `syntax.h` を include し `facade` が `:syntax` に依存するよう修正（1 つの的で `ParseDDL` と `ValidateDDL` の両方を公開）。(2) パイプラインの順序を `validate-build` → `fix_build_json` に直して再実行。`validate-build` はキャッシュが効く見込み。`wasm-build` は直列実行なので、約 5,000 手順で数時間かかる見込み
- 判断: wasmify の `wasm-build` に並列実行の選択肢は無い（ソース確認）。長時間かかるのは受け入れる
- 06:20 **P3 再実行**: `validate-build` は全 8,860 手順がキャッシュ命中（1 秒）。`fix_build_json` で 5,818 手順の skip を解除（残り 4）。`gen-proto` は `ParseDDL` と `ValidateDDL` の 2 本を公開。`wasm-build` は 61 分走って 817 手順目の `backend/query/remote_udf/remote_udf_evaluator.cc` で停止: `httplib.h` 経由で `<net/if.h>` が要る（wasi に無い）。遠隔 UDF の HTTP 呼び出し用で、DDL 検証には不要
- 06:22 対処: ネットワーク系ヘッダを含む first-party ソースを洗い出して `skip.files` に入れ（`wasmify.json` と `tools/set_bridge.py` の両方）、`wasm-build` を再開。816 手順分はキャッシュされているので、続きから進む
- 06:35 `wasm-build` 再開は 892 手順目 `change_stream.grpc.pb.cc` で停止（gRPC の `port_platform.h` が wasm を判別できない）。調べると**残り約 5,470 手順のうち約 3,700 が gRPC 一式**（grpc core 1,332、boringssl 806、envoy_api 692、google_cloud_cpp 300、c-ares 182、xds 182、upb 106）。first-party のコードは gRPC をほぼ使っておらず（`common/config` の関数名のみ）、BUILD の `deps` に `@com_github_grpc_grpc//:grpc++` が約 90 箇所書かれていただけ
- 06:40 対処: `backend/` と `common/` の BUILD から `grpc++` の依存を機械的に削除、`spanner_cc_grpc` → `spanner_cc_proto` に置換（MODIFIED 注記付き）。ネイティブ再ビルドと `bazel query` で確認中。google-cloud-cpp の `bytes.h` を include する 2 ファイル（`transaction/actions.cc`、`actions/change_stream.cc`）は実際には `absl::Base64Escape` を使っていて include が死んでいるので、次に外す
- 見込み: gRPC 一式を外せば wasm のコンパイル対象は約 1,800 手順に減り、`wasm-build` の所要時間も 1 時間台に収まる
- 06:50 **gRPC 依存を外した木でネイティブビルド成功**（4 分、30 手順）。`bazel query` で `facade` の推移的依存に gRPC・boringssl・envoy・c-ares・xds は 0 件。編集した BUILD は 23 件
- 06:52 google-cloud-cpp の死んだ include（`google/cloud/spanner/bytes.h`、2 ファイル）と BUILD 依存も除去。記録の取り直しから `wasm-build` までを一続きで再実行中（依存が変わり引数も変わるため、`validate-build` と `wasm-build` の多くはキャッシュが効かず作り直しになる見込み: 合わせて 2 時間前後）
- 07:50 **gRPC 除去後の再記録**: 手順数 8,860 → 4,200（compile 2,532）。`validate-build` は全件キャッシュ。`gen-proto` は `ParseDDL` `ValidateDDL` の 2 本。`wasm-build` は 51 分走り、1,797 手順目 `googlesql/base/net/ipaddress_oss.cc`（NET 関数用）で `<net/if.h>` 不足により停止
- 07:55 対処: wasmify 同梱の stub ヘッダを `skip.deploy_stub_headers: ["net/if.h"]` で配置して再開（残り約 730 手順 ＋ リンク）。他に wasi に無いヘッダを直接 include するソースは 14 件あるが、いずれも wasmify の互換ヘッダ（`sys/socket.h` `netdb.h` `sys/mman.h` `dlfcn.h` など）で通る見込み
- 08:00 `net/if.h` の stub は効いた。次は 1,799 手順目 `googlesql/base/net/public_suffix_oss.cc`（NET.REG_DOMAIN 等）が libc++ で型変換エラー。外部の NET 関数実装で DDL 検証に不要
- 08:02 `wasm-build` を「外部ソースで失敗したら `skip.files` に加えて再開、first-party で失敗したら停止」のループで実行中（キャッシュにより 1 周は短い）
- 08:20 **本命版（`ValidateDDL`）の wasm が完成。** `spanner_emulator.wasm` 14.8 MB（wasm-opt 前 20.4 MB）。1,823 手順（compile 1,261、archive 556、skip 6、cache 1,441）、526 archive をリンク。自動除外ループは 2 周で成功（追加除外は `public_suffix_oss.cc` の 1 件）。`build/full/` に退避
- 08:30 **`ValidateDDL` が Go の中で動いた（wazero 版）。** 5 種の意味エラー（`Table not found: NoSuchTable` / `Column Y.A has type ARRAY, but is part of the primary key.` / `Table Z references nonexistent key column NoSuchCol.` / `Index Bad specifies key column NoSuchColumn which does not exist in the index's base table.` / `Duplicate name in schema: Singers.`）を本物のエミュレータと同じ文言で検出。正しい 3 文は通過。`ParseDDL` も同じバイナリで動作。テスト全体 1.2 秒（`ValidateDDL` 6 回で 0.04 秒）
- 08:31 wasm2go 版の生成は `tools/gen_go_host.sh` の不具合（buf の `--template` に拡張子無しの一時ファイルを渡すとインライン JSON と解釈される）で 1 回失敗。修正して再実行中
- 注記: 本命版 wasm の外部参照（env import）は 87 個。ほとんどが absl のログ関連（`skip.files` で外した `log/internal/globals.cc` 等）だが、`googlesql::GetDefaultErrorMessageStability` など googlesql の関数も含まれる。`facade` の BUILD 依存に不足がある可能性（cc_library は未定義シンボルを検出しない）。テストは通っているが、後で依存を足して 0 に近づける
- 08:40 本命 wasm の外部参照 87 個の正体: 大半が **ICU**（`u_toupper_76`、`icu_76::RuleBasedCollator` など）と absl のログ関連。ICU は `rules_foreign_cc`（configure/make）で作られるので wasmify の Bazel 記録に入らず、wasm にリンクされていない。ASCII の DDL 検証には影響しないが、非 ASCII の照合・大文字小文字変換を使う経路では正しく動かない。**課題: ICU を wasm 向けにビルドして `wasm_build.prebuilt_archives` で渡す**（wasmify にその設定がある。googlesql-wasm も同じ問題を通ったはず）
- 08:01 **wasm2go 版（純 Go、arm64）で `ParseDDL` と `ValidateDDL` のテスト成功。** 変換 7 分 17 秒・最大 13.3 GB（ホスト）。生成物 720 MB / 3,800 万行。テストはビルド込み 21 秒
- 08:15 本命版（純 Go）のクロスコンパイル:   linux/amd64 OK (57s)   linux/arm64 OK (19s)   windows/amd64 OK (56s) 

## 2026-09-09（朝、起床後）

- 08:25 Makefile の誤りを修正: `fix_build_json` をホスト側で `build` 直後に走らせていた（実行ルートが見えず効かない）。`headers` でコンテナ内、`validate-build` の後に実行するよう変更
- 08:28 **通し実行を開始**（`make classify STAGE=full → build → headers → bridge → proto → wasm → go-host → go test`）。Makefile と tools/ だけで再現できるかの確認
- 08:35 ICU の対処に着手。確認: `build.json` に ICU のコンパイル手順は 0 件（`rules_foreign_cc` の configure/make は Bazel の 1 アクションで、per-file の記録に出ない）。ネイティブの `libicuuc.a` 等は x86 なので使えない。ICU 76.1 のソースを `build/icu/src` に複製し、`tools/build_icu_wasm.sh` で「ホスト向けに道具をビルド → `--with-cross-build` で wasm32-wasip1 向けに静的ビルド」を実行中。できた `.a` は `wasm_build.prebuilt_archives` で wasmify に渡す
- 判断（配布）: wazero 版も cgo 不要の単一バイナリなので、**spnls にはまず wazero 版（wasm 14.8 MB 同梱）を組み込む**。純 Go 版（720 MB）は別モジュールで後から
- 08:50 **wasm2go の不具合の原因を訂正**: 玩具で 4 通り試した結果、arm64 アセンブリが壊れるのは **import path にハイフンが含まれるとき**（3 万行混入）。モジュール配下かどうかは無関係（ハイフン無しなら配下でも 0 行）。amd64 は常に無傷。`go-spanner-analyzer` にハイフンがあるため配下に置くと踏んだ、が正しい説明。再現手順を `docs/wasm2go-arm64-hyphen.md` に記録
- 08:45 **ICU 76.1 を wasm32-wasip1 向けにビルドできた**（`tools/build_icu_wasm.sh`、11 分）: `libicuuc.a` 2.7 MB、`libicui18n.a` 4.8 MB。ICU の `configure` は wasm を知らないので `mh-linux` を使うよう 1 行足した。最後の `packagedata` だけ失敗（ICU の `genccode` が wasm の .o を ELF として読めない）→ データは `genccode -e icudt76`（C 配列出力）→ wasi clang でコンパイル → `libicudata.a` 31.9 MB、として別途作成。入口シンボルは `icudt76_dat`
- 次: 通し実行の完了後、`wasm_build.prebuilt_archives` に 3 つを渡して wasm を作り直し、外部参照 87 個の減少と wazero 版テストを確認
- 09:57 判断: 通し実行の `make wasm --no-cache` は 85 分で 307/1,261（googlesql の大きなファイル群で 1 分/ファイル、直列・Rosetta）。数時間かかるので**中断**。Makefile の `wasm` は既定でキャッシュを使うよう変更し、全部作り直しは `NOCACHE=1` に。クリーンな作り直しの確認は Linux（CI）で行う方針
- 09:58 `make bridge STAGE=full` で ICU の 3 つの `.a` を `wasm_build.prebuilt_archives` に入れ、キャッシュ利用で `make wasm` → wasm を作り直し中。続けて外部参照の数と wazero 版のテストを確認
- 10:25 **ICU を組み込んだ wasm が完成。** `spanner_emulator.wasm` 46.4 MB（最適化前 51.5 MB。ICU のデータ 32 MB を含む）。外部参照は env 87 → **45、ICU 由来は 0**。wazero 版で `ParseDDL` / `ValidateDDL` のテスト通過。成果物は `build/full-icu/`
- ~~残課題（ICU 関連）: wasm 46 MB~~ → **解決**（12:12）: ICU データを 31.9 MB → 2.0 MB に絞り、wasm は 46.4 MB → **17.4 MB**
- 10:40 ICU のデータを絞る作業を開始。方針（作者の判断）: 大文字小文字を同一視する比較ができれば十分。`tools/icu-filter.json`（additive: 正規化・照合の基本データ・root ロケール・misc のみ）でホスト側のデータだけ作り直し → `libicudata.a` を作り直し → wasm を再リンク → 大きさ・外部参照・テストを確認中
- 11:55 絞り込み 1 回目は効かなかった（.dat が 31.9 MB のまま）。原因: googlesql が使う ICU の配布物には**元データ（coll/ locales/ 等の .txt）が無く、事前ビルド済みの `data/in/icudt76l.dat` だけが同梱**されている。`ICU_DATA_FILTER_FILE` はソースからデータを作るときにしか効かない
- 12:00 対処: ICU 同梱の道具 `icupkg` で事前ビルド済みの .dat から不要な項目を**取り除く**方式に変更（`icupkg -l` で一覧 → 残すもの以外を `-r` で削除）。残すのは正規化（`*.nrm`）、照合の基本（`ucadata.icu`、`coll/root.res`）、root ロケール、共通表（`supplementalData` 等）
- 12:12 **ICU データの絞り込み成功。** `icupkg` で 4,136 項目 → 23 項目（正規化 `nfkc*.nrm` `uts46.nrm`、照合の基本 `coll/ucadata.icu` `coll/root.res`、root ロケール、共通表）。`libicudata.a` 31.9 MB → **2.0 MB**。wasm は 46.4 MB → **17.4 MB**（最適化前 24.2 MB）。wazero 版テスト通過。残すものの一覧は `tools/icu-keep.txt`、手順は `tools/build_icu_wasm.sh` に反映
- 12:15 絞った wasm から純 Go 版（wasm2go）を再生成中（ホスト）
- 12:39 **絞った wasm（17.4 MB）から純 Go 版を再生成、テスト通過。** 生成 11 分半（ホスト）。生成物 749 MB / 3,950 万行、空スタブ 45（wasm の実 import と一致）。arm64 ネイティブ `CGO_ENABLED=0` で `ParseDDL` `ValidateDDL` 通過、linux/amd64・linux/arm64 へクロスコンパイル可。成果物は `build/trim-wasm2go-host/`。これが `spanneranalyzerwasm2go` として公開する候補
- 13:12 **バンドルを公開（非公開リポジトリ）**: `github.com/tyzerrr/spanneranalyzerwasm2go` v0.1.0（749 MB のソース、git の圧縮後 175 MB。Apache-2.0、NOTICE・THIRD_PARTY_NOTICES 同梱）
- 13:15 **API 側を整備**: `go-spanner-analyzer` の root に `go.mod`（`replace` なしでバンドル v0.1.0 に依存）、`spanneranalyzer.go`、`doc.go`、テスト 2 本を配置。`go mod tidy` と純 Go でのテストを通し、v0.1.0 としてタグ付け。非公開リポジトリなので利用側は `GOPRIVATE=github.com/tyzerrr/*` が要る
- 13:20 **Go モジュールの上限（1 モジュール 500 MiB）に引っかかった。** 749 MB のバンドルは `go get` で `module source tree too large` になる（goccy の前例は 388 MB で収まっている）。対処: バンドルを入れ子モジュールに分割（root、`base`、`p0`〜`p11` の 14 モジュール。各 51〜77 MB。import path は不変。依存は root → p11 → p10 → … → p0 → base の一方向）。タグは `base/v0.1.1` `p0/v0.1.1` … `v0.1.1`。壊れていた v0.1.0 のタグは両リポジトリから削除
- 13:23 **利用者の立場での確認に成功**: まっさらな一時モジュールで `go get github.com/tyzerrr/go-spanner-analyzer@v0.1.1` → 入れ子の 14 モジュールが取得され、`CGO_ENABLED=0 go run` で `ValidateDDL` が `Index Bad specifies key column NoSuchColumn ...` を返した（取得 15 秒、初回ビルド 32 秒）
- 13:30 API リポジトリ内の `go mod tidy` が `build/` 以下の生成物（古い import path を持つ）を拾って失敗し、`go.sum` の無いまま v0.1.1 を出してしまった（利用側は自分で go.sum を作るので動いていた）。`build/go.mod` を置いてモジュール境界の外に出し、`go.sum` を入れて **v0.1.2** として出し直し
