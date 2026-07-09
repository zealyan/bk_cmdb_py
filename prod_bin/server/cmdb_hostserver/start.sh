#!/bin/bash

set -e

# get local IP.
localIp=`python ip.py`

# make log-dir if not exists.
if [[ ! -d "./logs" ]];then
    mkdir ./logs
fi

# set execute 
chmod +x cmdb_hostserver
./cmdb_hostserver --addrport=${localIp}:60001 --logtostderr=false --log-dir=./logs --v=log_level_placeholder --regdiscv=rd_server_placeholder extend_flag_placeholder > ./logs/std.log 2>&1 &
