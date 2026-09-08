#!/usr/bin/env bash
# ICU を wasm32-wasip1 向けに静的ビルドする（wasmify のコンテナ内で実行する）。
# googlesql は ICU を rules_foreign_cc で作るため wasmify の記録に入らず、
# そのままでは wasm に ICU がリンクされない。ここで作った .a を
# wasmify.json の wasm_build.prebuilt_archives で渡す。
#
# 手順: ICU の交差ビルドはホスト用の道具（genccode 等）が要るので、
#   1) ホスト向けに一度ビルド（道具を得る） 2) --with-cross-build で wasm 向けにビルド
set -euo pipefail
SRC=${1:-/work/build/icu/src}         # ICU 76.1 のソース（bazel の external からの複製）
OUT=${2:-/work/build/icu}
WASI=${WASI_SDK:-/root/.config/wasmify/bin/wasi-sdk}
JOBS=${JOBS:-6}
CONF="--enable-static --disable-shared --disable-dyload --disable-extras --disable-plugins --disable-tests --disable-samples --with-data-packaging=static"

# configure は wasm を知らず mh-unknown に落ちるので、mh-linux を使うよう 1 行足す（複製に対してのみ）
if ! grep -q 'wasm\*-\*-\*) icu_cv_host_frag=mh-linux' "$SRC/source/configure"; then
  sed -i.bak 's|^\*-\*-linux\*|\*-\*-gnu|\*-\*-k\*bsd\*-gnu|\*-\*-kopensolaris\*-gnu) icu_cv_host_frag=mh-linux ;;|wasm*-*-*) icu_cv_host_frag=mh-linux ;;\n&|' "$SRC/source/configure"
  grep -n 'wasm\*-\*-\*' "$SRC/source/configure" | head -2
fi

echo "==> [1/2] ホスト向けビルド（道具のため）: $OUT/host"
mkdir -p "$OUT/host" && cd "$OUT/host"
if [ ! -f bin/genccode ] && [ ! -f lib/libicuuc.a ]; then
  "$SRC/source/runConfigureICU" Linux $CONF --enable-tools > configure-host.log 2>&1 || { tail -30 configure-host.log; exit 1; }
  make -j"$JOBS" > make-host.log 2>&1 || { tail -40 make-host.log; exit 1; }
fi
ls bin | head -5

echo "==> [2/2] wasm32-wasip1 向けビルド: $OUT/wasm"
mkdir -p "$OUT/wasm" && cd "$OUT/wasm"
export CC="$WASI/bin/clang" CXX="$WASI/bin/clang++" AR="$WASI/bin/llvm-ar" RANLIB="$WASI/bin/llvm-ranlib" STRIP="$WASI/bin/llvm-strip"
COMMON="--target=wasm32-wasip1 --sysroot=$WASI/share/wasi-sysroot -O2 -fno-omit-frame-pointer -D_WASI_EMULATED_MMAN -D_WASI_EMULATED_SIGNAL -D_WASI_EMULATED_PROCESS_CLOCKS -DU_HAVE_MMAP=0 -DU_HAVE_POPEN=0 -DU_HAVE_TZSET=0 -DU_HAVE_TZNAME=0 -DU_HAVE_TIMEZONE=0 -DU_HAVE_DIRENT_H=0 -DU_HAVE_NL_LANGINFO_CODESET=0 -DU_TIMEZONE_PACKAGE= -mllvm -wasm-enable-sjlj"
export CFLAGS="$COMMON" CXXFLAGS="$COMMON -std=c++17" CPPFLAGS="" LDFLAGS="-lwasi-emulated-mman -lwasi-emulated-signal -lwasi-emulated-process-clocks"
"$SRC/source/configure" --host=wasm32-wasi --with-cross-build="$OUT/host" $CONF --disable-tools --disable-icuio > configure-wasm.log 2>&1 || { tail -40 configure-wasm.log; exit 1; }
make -j"$JOBS" > make-wasm.log 2>&1 || { tail -60 make-wasm.log; exit 1; }
echo "==> 生成物"
ls -la lib/*.a
file lib/libicuuc.a 2>/dev/null || true
"$AR" t lib/libicuuc.a | head -3
echo "==> wasm32 のオブジェクトか確認"; "$WASI/bin/llvm-objdump" -h lib/libicuuc.a 2>/dev/null | grep -m1 "file format"
