#!/usr/bin/bash
# set -e
export CWD=$(dirname $(readlink -f ${BASH_SOURCE[0]}))
export PROJ_ROOT=$CWD/../../../
PORT=9999

export ROBOCHAN_LOGLEVEL=${ROBOCHAN_LOGLEVEL:-0}
export ROBOIMPL_LOGLEVEL=${ROBOIMPL_LOGLEVEL:-0}
export VRE_VIDEO_LOGLEVEL=${VRE_VIDEO_LOGLEVEL:-0}

function wait_for_start {
    n_tries=$1
    port=$2
    i=0
    while (( i < n_tries )); do
        res=$(lsof -i udp:$port -t)
        if [ "$?" == "0" ]; then
            echo "---- Found pid after $i tries"
            return 0
        fi
        i=$((i+1))
        sleep 0.1
    done
    kill $$
}

function cleanup {
    kill $PID_FFMPEG $PID_MAIN
    rm -f frame.png
}

echo "End to end test: Video + UDP listener"

echo "-- Initial cleanup"
( kill $(lsof -i udp:$PORT -t) 2>/dev/null ) || echo "---- No server to kill on port $PORT"
rm -f frame.png # uses "cwd" of the user

# ffmpeg -i https://w3.webcamromania.ro/busteni/index.m3u8  -f rawvideo -pix_fmt rgb24 - 2>/dev/null | \
#     ./main.py - --port 42069 --frame_resolution 800 1280 --fps 30^
# $CWD/main.py $CWD/test_video.mp4 --port $PORT &
ffmpeg -i $CWD/test_video.mp4 -f rawvideo -pix_fmt rgb24 - 2>/dev/null | \
    $CWD/main.py - --port $PORT --frame_resolution 720 1280 --fps 30 &
PID_MAIN=$!
PID_FFMPEG=$(ps -ef | grep ffmpeg | head -n 1 | tr -s "  " " " | cut -d " " -f2)
wait_for_start 100 $PORT

echo "-- Sending 'RANDOM'"
res=$(echo "RANDOM" | nc -w1 -u 127.0.0.1 $PORT)
expected="Unknown message: RANDOM"
test "$res" == "$expected" && echo "---- OK" || { echo -e "----Expected $expected.\n----Got $res."; cleanup; exit 1; }

echo "-- Sending 'GO_FORWARD 1'"
res=$(echo "GO_FORWARD 1" | nc -w1 -u 127.0.0.1 $PORT)
expected="OK"
test "$res" == "$expected" && echo "---- OK" || { echo -e "----Expected $expected.\n----Got $res."; cleanup; exit 1; }

echo "-- Sending 'TAKE_SCREENSHOT'"
res=$(echo "TAKE_SCREENSHOT" | nc -w1 -u 127.0.0.1 $PORT)
expected="OK"
test "$res" == "$expected" && echo "---- OK" || { echo -e "----Expected $expected.\n----Got $res."; cleanup; exit 1; }

echo "-- Checking frame.png"
[[ -f frame.png && $(head -c 4 frame.png) == $'\x89PNG' ]] \
  && echo "---- OK: Valid PNG" || { echo "----Invalid or missing PNG"; cleanup; exit 1; }

echo "ALL OK"
cleanup
