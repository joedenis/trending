#!/bin/bash


STRING="**************Launching Praescire update .csv of prices*************"
ROOT="/home/joe/PycharmProjects/trending/trending/backtests/"
PYTHON="/home/joe/PycharmProjects/trending/venv/bin/python"
GAME="praescire_closing_prices.py"

pushd . > /dev/null 2>&1

cd $ROOT

printf "********************************************************************\n"
echo $STRING
printf "********************************************************************\n"

export PYTHONPATH=/home/joe/PycharmProjects/trending
$PYTHON "$GAME"

popd > /dev/null 2>&1


STRING_2="*************Launching backtest to generate the tearsheet***********"

GAME_2="buyhold.py"

pushd . > /dev/null 2>&1
cd $ROOT

printf "*******************************************************************\n"
echo $STRING_2
printf "*******************************************************************\n"
export PYTHONPATH=/home/joe/PycharmProjects/trending
$PYTHON "$GAME_2"

popd > /dev/null 2>&1

cp /home/joe/PycharmProjects/trending/trending/data/PRAESCIRE21.csv  /home/joe/PycharmProjects/quantstats_git/quantstats/data/

export PYTHONPATH=/home/joe/PycharmProjects/quantstats_git
cd /home/joe/PycharmProjects/quantstats_git
source venv/bin/activate

python quantstats/samples/tester1.py
python quantstats/samples/updateTimestampWebsite.py

deactivate

printf "*********copying .html to hugo directory **********\n"

cp /home/joe/PycharmProjects/quantstats_git/quantstats/savedcharts/PRAESCIRE21.html /home/joe/Websites/loveit/static/results

firefox /home/joe/Websites/loveit/static/results/PRAESCIRE20.html
