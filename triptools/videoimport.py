#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import calendar
from datetime import datetime
import pytz
import logging
import os
from pynmea.nmea import GPRMC, GPGGA
from pynmea.streamer import NMEAStream
from imageio.plugins import ffmpeg
import re
import shlex
import subprocess
import sys
import types

from triptools import config
from triptools import DB

logging.basicConfig(level=logging.INFO)

TIME_EXPR = re.compile(r"^(\d\d):(\d\d):(\d\d),(\d\d\d) --> .*$")

def parse_nmea_time(gprmc):
    if gprmc.datestamp and gprmc.timestamp:
        ts_str = "%s20%s %s" % (gprmc.datestamp[0:4], gprmc.datestamp[4:], gprmc.timestamp[0:6])
        dt = datetime.strptime(ts_str, "%d%m%Y %H%M%S")
        ts = calendar.timegm(dt.utctimetuple())
        return ts
    else:
        return None

def nmeaToFloat(nmeaStr):
    if nmeaStr:
        floatVal = float(nmeaStr) / 100.0
        deg = int(floatVal)
        mins = floatVal - deg
        return deg + mins/6.0*10
    else:
        return None

def fetch_duration(filename):
    expr = re.compile("\s+Duration: (\d{2}):(\d{2}):(\d{2}).(\d{2}),.*")
    args = [ffmpeg.get_exe(), "-i", filename]
    seconds = None
    with subprocess.Popen(args, stderr=subprocess.PIPE) as job:
        for line in job.stderr:
            line = line.decode("ascii", "ignore")
            m = expr.match(line)
            if m:
                return (int(m.group(1)) * 3600
                        + int(m.group(2)) * 60
                        + int(m.group(3))
                        + int(m.group(4))/100.0)

    raise Exception("Failed to fetch duration")

def fetch_videopoints(filename):
    args = [ffmpeg.get_exe()] + shlex.split("-loglevel 8 -i") + [filename] + shlex.split("-map 0:s:0 -f srt -")

    start_time_guesses = {}
    points = []
    
    offset = None
    stream = NMEAStream()
    lon = None
    lat = None
    alt = None
    with subprocess.Popen(args, stdout=subprocess.PIPE) as job:
        count = 0
        for line in job.stdout:
            line = line.decode("ascii").strip()
            if not line:
                continue
            match = TIME_EXPR.match(line)
            if match:
                offset = int(match.group(1)) * 3600 + int(match.group(2)) * 60 + int(match.group(3))
            else:
                pos = line.find("$GP")
                if pos != -1:
                    line = line[pos:]
                if line.startswith("$"):
                    o = stream.get_objects(data=line)
                    if o:
                        o = (o[0])
                        lon = None
                        lat = None
                        if isinstance(o, GPRMC):
                            time_t = parse_nmea_time(o)
                            if offset and time_t:
                                start_time_guesses[time_t - offset] = start_time_guesses.setdefault(time_t - offset, 0) + 1
                            lon = nmeaToFloat(o.lon)
                            lat = nmeaToFloat(o.lat)
                            if o.lon_dir == "W":
                                lon = -lon
                            if o.lat_dir == "S":
                                lat = -lat
                        elif isinstance(o, GPGGA):
                            lon = nmeaToFloat(o.longitude)
                            lat = nmeaToFloat(o.latitude)
                            if o.lon_direction == "W":
                                lon = -lon
                            if o.lat_direction == "S":
                                lat = -lat
                            if o.altitude_units == "M" and o.antenna_altitude:
                                alt = float(o.antenna_altitude)
                        if lon is not None and lat is not None and alt is not None:
                            try:
                                points.append((lon, lat, alt, offset))
                                lon = lat = alt = None
                            except:
                                import traceback
                                traceback.print_exc()
    # find best guess
    guess_list = list(start_time_guesses.items())
    guess_list.sort(key=lambda a:a[1])
    return points, guess_list[-1][0]
    
def import_videopoints(filename):

    duration = fetch_duration(filename)

    count = 0
    points, start_time = fetch_videopoints(filename)

    with DB() as db:
        video_id = db.get_video_id(filename, start_time=start_time, duration=duration)
        db.remove_points(video_id)

        for lon, lat, alt, offset in points:
            try:
                count += db.add_video_point(lon, lat, alt, offset+start_time, video_id)
            except:
                import traceback
                traceback.print_exc()

    logging.getLogger(__name__).info("file '%s' imported, %d videopoints added to DB" % (filename, count))
            
if __name__ == "__main__":

    try:
        filename = config.get("Video", "name")
        filename = os.path.abspath(filename)
        if not os.access(filename, os.R_OK):
            raise Exception("cannot read video file '%s'" % filename)

        import_videopoints(filename)
        
    except Exception as e:
        logging.getLogger(__name__).error(e, exc_info=True)
        sys.exit(1)
