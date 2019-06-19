#!/usr/bin/env bash

# 1st parameter: database name
# 2nd parameter: ripe atlas API key
# 3rd parameter: path to hloc installation
# 4th parameter (optional): a path to a file with ips

filedate=`date +%Y-%m-%d-%H-%M`
# 180 days of allowed measurement age
allowedMeasurementAge=15552000

if [[ -z $1 ] || [ -z $2 ] || [ ! -d $3 ] || [ ! -d $4 ]]; then
    echo "provide the database name, the RIPE Atlas API key, and the hloc directory! Aborting!"
    exit 1
else
    logPath="logs"
    if [[ ! -d ${logPath} ]]; then
        mkdir ${logPath}
    fi

    logPath=$(realpath ${logPath})

    cd $3

    if [[ ! -f "/var/cache/hloc/ripe_probes.cache" ] || [ `psql -d $1 -U hloc -tc "SELECT count(*) from probes"` -eq 0 ]]; then
        ./hloc/cache_ripe_probes.sh $3 $1
    fi

    if [[ $# -eq 4 ] && [ -e $4 ]]; then
        python3 -m hloc.scripts.validate --number-processes 10 --ripe-request-limit 30 --ripe-request-burst-limit 50 --measurement-limit 100 --allowed-measurement-age ${allowedMeasurementAge} --buffer-time 0 --measurement-strategy aggressive --api-key $2 --include-ip-encoded --use-efficient-probes --probes-per-measurement 1 --measurement-packets 1 --database-name $1 --ip-filter-file $4 -l ${logPath}/validate-multi.log -ll DEBUG
    elif [[ $# -eq 3 ]]; then
        python3 -m hloc.scripts.validate --number-processes 10 --ripe-request-limit 30 --ripe-request-burst-limit 50 --measurement-limit 100 --allowed-measurement-age ${allowedMeasurementAge} --buffer-time 0 --measurement-strategy aggressive --api-key $2 --include-ip-encoded --use-efficient-probes --probes-per-measurement 1 --measurement-packets 1 --database-name $1 -l ${logPath}/validate-multi.log -ll DEBUG
    else
        echo "Either not the correct amount of properties was given or IP-List file could not be found!"
    fi
fi
