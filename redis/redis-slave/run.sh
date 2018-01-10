#!/bin/bash
sed -i "s/%master-ip%/${REDIS_MASTER_SERVICE_IP}/" /etc/redis/redis.conf
sed -i "s/%master-port%/{REDIS_MASTER_SERVICE_PORT}/" /etc/redis/redis.conf
redis-server /etc/redis.conf --slaveof ${REDIS_MASTER_SERVICE_HOST} 6379
