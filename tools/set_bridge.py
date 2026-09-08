#!/usr/bin/env python3
"""wasmify.json の bridge / skip 節を書く。使い方: python3 tools/set_bridge.py syntax|full"""
import json, sys
stage = sys.argv[1] if len(sys.argv) > 1 else "syntax"
p = "wasmify.json"
d = json.load(open(p))
exports = ["spanner_analyzer::ParseDDL"]
if stage == "full":
    exports.append("spanner_analyzer::ValidateDDL")
d["bridge"] = {
    "ExportFunctions": exports,
    # googlesql-wasm と同じ: absl / protobuf の型はブリッジせず素通しにする
    "ExternalTypes": [
        "absl::Status", "absl::StatusOr", "absl::string_view", "absl::Span",
        "absl::Time", "absl::TimeZone",
        "googlesql_base::Status", "googlesql_base::StatusOr",
        "RE2",
        "google::protobuf::Descriptor", "google::protobuf::DescriptorPool",
        "google::protobuf::EnumDescriptor", "google::protobuf::EnumValueDescriptor",
        "google::protobuf::FieldDescriptor", "google::protobuf::FileDescriptor",
        "google::protobuf::FileDescriptorProto", "google::protobuf::FileDescriptorSet",
        "google::protobuf::OneofDescriptor",
    ],
    "ErrorTypes": {
        "absl::Status": "if (!{result}.ok()) { _pw.write_error(std::string({result}.message())); }",
        "absl::StatusOr": "if (!{result}.ok()) { _pw.write_error(std::string({result}.status().message())); }",
        "googlesql_base::Status": "if (!{result}.ok()) { _pw.write_error(std::string({result}.message())); }",
        "googlesql_base::StatusOr": "if (!{result}.ok()) { _pw.write_error(std::string({result}.status().message())); }",
    },
    "GoPackage": "github.com/tyzerrr/go-spanner-analyzer;spanneranalyzer",
    # wasm2go の import path に **ハイフンを含めない**（wasm2go v0.5.15 の arm64 出力が壊れる。
    # 玩具で切り分け済み: ハイフン有り→ 3 万行混入、無し→ 0。モジュール配下かどうかは無関係）。
    # モジュール名 go-spanner-analyzer にハイフンがあるので、モジュール外の別パスにしている。
    "Wasm2GoImportPath": "github.com/tyzerrr/spanneranalyzerwasm2go",
}
# googlesql-wasm が wasi で除外している absl のファイル（ホスト依存）
# wasi に無いヘッダは wasmify 同梱の stub を配置する（googlesql の NET 関数が net/if.h を使う）
d["skip"] = {"deploy_stub_headers": ["net/if.h"], "files": [
    {"path": "external/abseil-cpp~/absl/debugging/symbolize.cc", "reason": "stack symbolization is host-platform-specific and not bridgeable to wasi"},
    {"path": "external/abseil-cpp~/absl/debugging/stacktrace.cc", "reason": "stack unwind helpers depend on host arch (no wasm32 backend)"},
    {"path": "external/abseil-cpp~/absl/base/internal/raw_logging.cc", "reason": "uses platform-specific syscalls; logging is unused in the bridged API surface"},
    {"path": "external/abseil-cpp~/absl/time/internal/cctz/src/time_zone_libc.cc", "reason": "libc time-zone backend not present in wasi-libc"},
    {"path": "backend/query/remote_udf/remote_udf_evaluator.cc", "reason": "uses httplib.h; networking is not available under wasi and not needed for DDL validation"},
    {"path": "external/abseil-cpp~/absl/log/internal/globals.cc", "reason": "uses platform-specific log infrastructure; bridged API surface does not log"},
]}
json.dump(d, open(p, "w"), indent=2, ensure_ascii=False)
print(f"bridge written for stage={stage}: {exports}")
