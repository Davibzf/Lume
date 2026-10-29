#!/usr/bin/env bash
set -euo pipefail
root="$(cd "$(dirname "$0")/.." && pwd)"
version=8.0.1
digest=05ee0b03119b45c0bdb4df654b96802e909e0a752f72e4fe3794f487229e5a41
mkdir -p "$root/vendor/sources" "$root/output/runtime"
archive="$root/vendor/sources/ffmpeg-$version.tar.xz"
curl --fail --location --retry 3 "https://ffmpeg.org/releases/ffmpeg-$version.tar.xz" -o "$archive"
echo "$digest  $archive" | sha256sum --check
tar -xf "$archive" -C "$root/vendor/sources"
cd "$root/vendor/sources/ffmpeg-$version"
./configure \
  --target-os=mingw32 --arch=x86_64 --cpu=x86-64 --enable-cross-compile \
  --cross-prefix=x86_64-w64-mingw32- --extra-ldflags=-static \
  --disable-autodetect --disable-shared --enable-static --disable-debug \
  --disable-doc --disable-ffplay --disable-ffprobe --disable-network \
  --disable-devices --disable-hwaccels --disable-bsfs \
  --disable-encoders --enable-encoder=pcm_s16le \
  --disable-muxers --enable-muxer=wav \
  --disable-filters --enable-filter=aformat,anull,aresample \
  --disable-decoders \
  '--enable-decoder=aac*,ac3*,adpcm_*,alac,amr*,ape,atrac*,dca,eac3,flac,gsm*,ilbc,mp1*,mp2*,mp3*,opus,pcm_*,qcelp,ralf,sbc,shorten,sipr,speex,tak,tta,twinvq,vorbis,wavpack,wma*' \
  --disable-protocols --enable-protocol=file,pipe
make -j"${BUILD_JOBS:-2}" ffmpeg.exe
x86_64-w64-mingw32-strip ffmpeg.exe
cp ffmpeg.exe "$root/output/runtime/ffmpeg.exe"
cp COPYING.LGPLv2.1 "$root/output/runtime/FFmpeg-LGPL-2.1.txt"
cp "$archive" "$root/output/runtime/ffmpeg-$version-source.tar.xz"
{
  echo "FFmpeg $version — LGPL v2.1 or later, no external codec libraries."
  echo "Source: https://ffmpeg.org/releases/ffmpeg-$version.tar.xz"
  echo "SHA256: $digest"
  echo "Build recipe: scripts/build_ffmpeg.sh in Davibzf/Lume."
  cat ffbuild/config.mak
} > "$root/output/runtime/FFmpeg-build.txt"
