#!/bin/bash
airflow db init
if ! airflow users list | grep -q "admin"; then
  airflow users create --username admin --firstname Admin --lastname User --role Admin --email admin@maritime.com --password maritime_admin
fi
