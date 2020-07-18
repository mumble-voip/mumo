#!/usr/bin/env bash

if [ "${TRAVIS_PULL_REQUEST}" == "false" ]; then
  echo "$DOCKER_PASSWORD" | docker login -u "$DOCKER_USERNAME" --password-stdin
fi

docker build -t mumo .
docker images

if [ "${TRAVIS_PULL_REQUEST}" == "false" ]; then
  docker tag mumo mumblevoip/mumo
  docker push mumblevoip/mumo
fi
