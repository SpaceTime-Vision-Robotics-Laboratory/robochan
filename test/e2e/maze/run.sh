#!/usr/bin/bash
set -e
export CWD=$(dirname $(readlink -f ${BASH_SOURCE[0]}))
export PROJ_ROOT=$CWD/../../../

export ROBOCHAN_LOGLEVEL=1
export ROBOIMPL_LOGLEVEL=1

seed=$(shuf -i 1-1000 -n 1)
python $PROJ_ROOT/examples/maze/main.py random --seed=${seed} --results_path $CWD/results.csv
python $PROJ_ROOT/examples/maze/main.py strategy1 --seed=${seed} --results_path $CWD/results.csv
echo "================================================================================"
cat $CWD/results.csv
