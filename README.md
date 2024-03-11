# mumo - The Mumble moderator
Mumo is meant to provide a platform on which python based Mumble server ICE extension modules can be built upon. The goal is to reduce the boilerplate needed
to interact with the Mumble server to a minimum.

To achieve this goal tasks like Ice interface setup, basic error
handling, configuration management, logging and more are provided
by mumo. Developers can focus on their specific functionality instead.

## Documentation
The documentation can be found in our wiki, see https://wiki.mumble.info/wiki/Mumo.

## Docker image
An official docker image is available at https://hub.docker.com/r/mumblevoip/mumo.
ALl the documentation is inside the wiki.

## Modules for Mumble moderator
### Included modules
Currently mumo comes with the following modules:
 * ***bf2***

 Battlefield 2 game management plugin that can dynamically move players into appropriate channels and groups to fit the in-game command structure. This is achieved by using data gathered from Mumble's positional audio system and does not require cooperation by the game server.

 * ***idlemove***

 Plugin for moving players that have been idle for a configurable amount of time into a idle channel. Optionally the players can be muted/deafened on move.

 * ***onjoin***

 Moves players into a specific channel on connect regardless of which channel they were in when they left last time.

 * ***seen***

 Makes the server listen for a configurable keyword to ask for the last time a specific nick was seen on the server.

 * ***source***

 Source game management plugin that can dynamically move players into on-the-fly created channel structures representing in-game team setup. This is achieved by using data gathered from Mumble's positional uadio system and does not require cooperation by the game server. Currently the following source engine based games are supported: Team Fortress 2, Day of Defeat: Source, Counter-Strike: Source, Half-Life 2: Deathmatch.

 * ***test***

 A debugging plugin that registers for all possible events and outputs every call with parameters into the debug log.

### 3rd party modules
See https://wiki.mumble.info/wiki/Mumo#3rd_Party_Modules

## Development
If you have a module that you would like to see shipped with mumo or
have any improvements or suggestions please contact us. Whether you
prefer a pull request, visiting us in IRC in #mumble on Freenode or
creating an issue with a diff-patch is up to you.

## Setting up
To configure and run mumo take a look at the mumo.ini and the module
specific configurations in modules-available folder. Enabling modules
is done by linking the configuration in modules-available to the
modules-enabled folder.

## Requirements
mumo requires:
* python >=3.2
* python3-zeroc-ice
* murmur >=1.2.3*

(* Not tested with lower versions yet.)
