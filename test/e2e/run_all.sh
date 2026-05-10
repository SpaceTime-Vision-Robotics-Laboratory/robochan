#!/usr/bin/bash
set -e
export CWD=$(dirname $(readlink -f ${BASH_SOURCE[0]}))

export ROBOCHAN_LOGLEVEL=2
export ROBOIMPL_LOGLEVEL=2

echo "================= Video UDP Screenshot ================="
bash $CWD/video-udp-screenshot/run.sh
echo "========================= Maze ========================="
bash $CWD/maze/run.sh
