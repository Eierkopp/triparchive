# triparchive

A collection of random tools to dabble with 

- Garmin GPS (Zumo 590)
- MTK track logger
- Contour +2
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
	% pip install -r requirements.txt

## osm_speedcams.sh

Automatically downloads traffic camera locations and converts them
into Garmin poi format. Requires [gpsbabel](https://www.gpsbabel.org/).


## videoimport.sh

Import GPS information from Contour +2 cam into a database. For each
position the filename and timestamp offset are saved. This will allow
a player to play a movie at a certain offset by clicking on a
trackpoint on a map. 

    % bin/videoimport.sh --video_name /tmp/FILE0023.MP4

## gpximport.sh

Import tracklogs from [GPX](www.topografix.com/gpx.asp) files. 

    % bin/gpximport.sh --gpx_name /tmp/current.gpx
	
## mtkimport.sh

Import tracklogs from an mtk track logger. Requires
[gpsbabel](https://www.gpsbabel.org/).

	% bin/mtkimport.sh --mtk_dev /dev/ttyACM0

## gnsimport.sh

Import country files from the [GNS](http://geonames.nga.mil/) website.

    % bin/gnsimport.sh --gns_country austria

## videomap.sh

Generate an overview map containing the tracklogs of all tracks
contained in video files selected by the given mask. Video files have
to be imported already for this command to produce useful output.

![sample map](https://cloud.githubusercontent.com/assets/6553148/19149564/c75b7b26-8bc2-11e6-93a0-9c45d5c84362.png)

    % bin/videomap.sh --video_mask=sauerland --map_width=400 --map_height=300
	
## trackmap.sh

Generate an overview map containing all tracklogs imported from a GPS
receiver. Trackpoints may be filtered by timestamp.

	% bin/trackmap.sh --track_start=2016-05-01T06:00:00 --track_end=2016-05-02T06:00:00

## geotagger.sh

Add EXIF information to image. GPS position is fetched from
trackpoints by matching timestamps. Location names are fetched from
geonetnames information by correlating location with data previously
imported with `gnsimport.sh`.

	% bin/geotagger.sh --photo_name DCIM0001.jpg
	
	

