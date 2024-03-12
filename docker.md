# Mumo Docker Image

[Docker](https://en.wikipedia.org/wiki/Docker_(software)) is a containerization and virtualization of applications and application environments.

An official docker image is available at https://hub.docker.com/r/mumblevoip/mumo.

## Network access to Mumble

Mumo accesses Mumble via the Ice interface. If you run Mumble Server in a docker container too, a network_mode configuration needs to be added so Mumo can access it.

If you are connecting to a non-containerized/generally-accessible Mumble Server this is not necessary.

The target is configured in `mumo.ini` with `host` and `port`.

## Data Volume - Configuration

`/data` is a Docker volume. You can bind your own folder to it for configuration and enabling and adding additional Mumo modules.

## Changing Enabled/Loaded Modules

When you add/enable new modules you need the restart the container.

## Running the Mumo Docker Image

The Mumo docker image can be run with:

```
docker run --name mumo --net=container:<id_of_mumble_server_container> -d -v /path/to/mumo/folder:/data mumblevoip/mumo
```

## Docker Compose

[Docker Compose](https://docs.docker.com/compose/) allows you to configure and run multi-container applications. This is useful to run a Mumble and Mumo container in a connected manner.

A docker-compose(v2.4) example:

```
    mumble-mumo:
        image: mumblevoip/mumo
        container_name: mumble-mumo
        restart: on-failure
        volumes:
            - /path/to/mumo/folder:/data
        network_mode : "service:mumble-server"
        depends_on:
            - mumble-server
```
