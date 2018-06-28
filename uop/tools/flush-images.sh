#!/bin/bash 

docker rmi -f $(docker images|grep -v "reg1.syswin.com/base"|awk '{if(NR!=1)print $3}')

