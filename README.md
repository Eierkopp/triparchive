# triparchive

A collection of random tools to dabble with 

- Garmin GPS (Zumo 590)
- Countour +2
- Digital camera

Development and testing is done exclusively on
[Debian Linux](http://www.debian.org) though most other distributions
should equally work. All tools require
[python3](http://www.python.org) and
[virtualenv](https://virtualenv.pypa.io/).

All tools require their environment in `triparchive_env` in the
installation directory. It can be created with 

    % /usr/bin/virtualenv -p python3 --always-copy triparchive_env
	% source ./triparchive_env/bin/activate
	% 

## osm_speedcams.sh

Automatically downloads traffic camera locations and converts them
into Garmin poi format. Requires [gpsbabel](https://www.gpsbabel.org/).


## videoimport.sh

Import GPS information from Contour +2 cam into a database. For each
position record filename and timestamp are saved.

