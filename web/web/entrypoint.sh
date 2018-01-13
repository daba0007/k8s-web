#!/bin/bash

sed -i "s/service_mysql/$(echo $MYSQL_MASTER_SERVICE_HOST)/g" /usr/src/dabaweb/dabaweb/settings.py

sed -i "s/service_redis/$(echo $REDIS_MASTER_SERVICE_HOST)/g" /usr/src/dabaweb/dabaweb/settings.py

#使用uwsgi来启动django
/usr/local/bin/uwsgi --http :8000 --chdir /usr/src/dabaweb -w dabaweb.wsgi
