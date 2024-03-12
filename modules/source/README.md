# Source Engine Module

The Source game management plugin for Mumo can dynamically move players into on-the-fly created channel structures representing in-game team setup.
This is achieved by using data gathered from Mumble's Positional-Audio and does not require cooperation by the game server.

The following source engine based games are supported:

* Team Fortress 2
* Day of Defeat: Source
* Counter-Strike: Source
* Half-Life 2: Deathmatch

## Enabling the `source` module

1. Link or copy the ''source.ini'' file from the `modules-available` folder into the `modules-enabled` folder\
  `cd modules-enabled`\
  `ln -s ../modules-available/source.ini`
2. Check whether the defaults in `source.ini` are ok for your setup. They should be sane for basic setups.
3. Restart mumo
