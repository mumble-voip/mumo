#!/usr/bin/env sh

if [ ! -f /data/mumo.ini ]
then
  cp /mumo/mumo.ini /data

  sed -i 's;level =.*;/level = 30;' /data/mumo.ini

  chmod a+rw /data/mumo.ini
  cp -r /mumo/modules-available /data
  mkdir -p /data/modules-enabled

  echo Created mumo default config data. Exiting.
  exit 1
fi

# Conf class don't read mumo.ini everytime to check custom folder
# so we copy them ...

cp -r /data/modules /mumo
cp -r /data/modules-available /mumo
cp -r /data/modules-enabled /mumo

exec "$@"
