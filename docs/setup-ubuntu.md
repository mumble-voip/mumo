# Setting up Mumo on Ubuntu Linux

*Note: This guide only shows the basic steps for trying out mumo. For a more permanent setup you'll want to run mumo with its own user and a startup script.*

## Prepare Mumble Server

Make sure you are running a recent Mumble Server release (1.2.4 or later).
In the Mumble Server configuration, Ice should be enabled and a writesecret must be set.

## Install Dependencies

```
sudo apt-get install python3-zeroc-ice python-daemon git
```

## Get and Configure Mumo

Clone the repository, in this example into `~/mumo`:

```
cd ~/
git clone https://github.com/mumble-voip/mumo.git
```

Adjust the Mumo configuration

```
cd mumo
nano mumo.ini
```

In the editor set your server's Ice writesecret as the secret variable so mumo can control your server.

```
secret = mysecretwritesecret
```

Close and save by pressing Ctrl + X followed by Y and Enter.

### Enable Modules

Configure the modules you want to use by editing their ini file in the `modules-available` folder.

Enable modules by linking their config file into the `modules-enabled` folder

```
cd modules-enabled
ln -s ../modules-available/moduleyouwanttouse.ini
```

## Running Mumo

```
./mumo.py
```

Mumo should now be working with your mumble server. If it doesn't work check the `mumo.log` file for more information.
