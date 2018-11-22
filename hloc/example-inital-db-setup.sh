#!/bin/bash

# TD:
# Tried to run: ./example-inital-db-setup.sh hloc "/dev/null" ".." ""
# in hloc/


# $1 is the database name
# $2 is the path to the rdns file
# $3 is the hloc directory
# $4 path to python environment

if [ -z $1 ] || [ -z $2 ] || [ -z $3 ] || [ ! -d $4 ]; then
    echo "a databasename, the rdns file, the hloc directory, and the python environment directory is needed! Aborting!"
    exit 1
else
    echo "if asked to recreate the db answer with yes (y)"
    source $4/bin/activate

    cd $3

    logPath="logs"
    if [ ! -d ${logPath} ]; then
        mkdir ${logPath}
    fi

    python3 -m hloc.scripts.codes_parser --database-name $1 -ao hloc/data/pages_offline -le "hloc/data/location-data/locodePart{}.csv" -c hloc/data/location-data/clli-lat-lon.txt -g hloc/data/location-data/cities1000.txt -e hloc/data/location-data/iata_metropolitan.txt -m 100 -p 100000 -l ${logPath}/codes-parsing -ll DEBUG -d

    if [ -e $2 ]; then
        python3 -m hloc.scripts.ipdns_parser $2 --database-name $1 --number-processes 8 -t hloc/data/location-data/tlds.txt --isp-ip-filter -l ${logPath}/dns-parsing -ll DEBUG
    else
        echo "the file ", $2, " does not exist"
        exit 2
    fi
fi
