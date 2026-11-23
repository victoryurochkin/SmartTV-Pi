#!/usr/bin/env bash
set -euo pipefail

repository=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
output=${1:-"$repository/dist/test-media"}
duration=12

command -v ffmpeg >/dev/null
command -v ffprobe >/dev/null
mkdir -p -- "$output"
cd -- "$output"

for rate in 30 60; do
    name="h264-1080p${rate}.mp4"
    printf 'Генерация %s\n' "$name"
    ffmpeg -hide_banner -loglevel error -y -filter_threads 1 \
        -f lavfi -i "testsrc2=size=1920x1080:rate=$rate:duration=$duration" \
        -f lavfi -i "sine=frequency=440:sample_rate=48000:duration=$duration" \
        -map 0:v:0 -map 1:a:0 -c:v libx264 -threads:v 2 -preset veryfast \
        -profile:v high -pix_fmt yuv420p -crf 22 -g "$((rate * 2))" \
        -color_range tv -colorspace bt709 -color_trc bt709 -color_primaries bt709 \
        -c:a aac -threads:a 1 -b:a 96k -movflags +faststart -shortest "$name"
done

name=hevc-main10-sdr-2160p30.mkv
printf 'Генерация %s\n' "$name"
ffmpeg -hide_banner -loglevel error -y -filter_threads 1 \
    -f lavfi -i "testsrc2=size=3840x2160:rate=30:duration=$duration,format=yuv420p10le" \
    -f lavfi -i "sine=frequency=440:sample_rate=48000:duration=$duration" \
    -map 0:v:0 -map 1:a:0 -c:v libx265 -threads:v 2 -preset ultrafast \
    -x265-params 'pools=1:frame-threads=1:lookahead-threads=1:log-level=error' \
    -profile:v main10 -pix_fmt yuv420p10le -crf 27 -g 60 \
    -color_range tv -colorspace bt709 -color_trc bt709 -color_primaries bt709 \
    -c:a aac -threads:a 1 -b:a 96k -shortest "$name"

audio="aevalsrc=0.18*sin(2*PI*440*t)|0.18*sin(2*PI*659.255*t):s=48000:d=$duration"
printf 'Генерация стереозаписей FLAC и WAV\n'
ffmpeg -hide_banner -loglevel error -y -filter_threads 1 -f lavfi -i "$audio" \
    -c:a flac -threads:a 1 -sample_fmt s32 -bits_per_raw_sample 24 \
    -metadata title='HomeTV Pi stereo test' stereo-48k-24bit.flac
ffmpeg -hide_banner -loglevel error -y -filter_threads 1 -f lavfi -i "$audio" \
    -c:a pcm_s16le -threads:a 1 stereo-48k-16bit.wav

clips=(h264-1080p30.mp4 h264-1080p60.mp4 hevc-main10-sdr-2160p30.mkv stereo-48k-24bit.flac stereo-48k-16bit.wav)
for clip in "${clips[@]}"; do
    printf '\n%s\n' "$clip"
    ffprobe -v error -of compact=p=0 \
        -show_entries stream=codec_name,profile,width,height,pix_fmt,r_frame_rate,sample_rate,channels,bits_per_raw_sample:format=duration \
        "$clip"
done | tee ffprobe.txt

sha256sum "${clips[@]}" > SHA256SUMS
