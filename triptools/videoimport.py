#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import logging
import os
from pynmea.streamer import NMEAStream
import re
import shlex
import subprocess
import sys
import types

from triptools import config
from triptools import DB

logging.basicConfig(level=logging.INFO)

TIME_EXPR = re.compile(r"^(\d\d):(\d\d):(\d\d),(\d\d\d) --> .*$")

def nmeaToFloat(nmeaStr):
    floatVal = float(nmeaStr) / 100.0
    deg = int(floatVal)
    mins = floatVal - deg
    return deg + mins/6.0*10

def import_videopoints(filename):

    db = DB()
    with db.conn() as conn:
        video_id = db.get_video_id(filename)
        db.remove_points(video_id)
        
        args = ["ffmpeg"] + shlex.split("-loglevel 8 -i") + [filename] + shlex.split("-map 0:s:0 -f srt -")

        offset = None
        lon = None
        lat = None
        stream = NMEAStream()
        with subprocess.Popen(args, stdout=subprocess.PIPE) as ffmpeg:
            count = 0
            for line in ffmpeg.stdout:
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
                            if "timestamp" in dir(o) and "datestamp" in dir(o) and o.lat and o.lon:
                                try:
                                    lon = nmeaToFloat(o.lon)
                                    lat = nmeaToFloat(o.lat)
                                    db.add_video_point(conn, lon, lat, offset, video_id)
                                    count += 1
                                except:
                                    pass

            logging.getLogger(__name__).info("file '%s' imported, %d videopoints added to DB" % (filename, count))
            
if __name__ == "__main__":

    try:
        filename = config.get("Video", "name")
        if not os.access(filename, os.R_OK):
            raise Exception("cannot read video file '%s'" % filename)

        import_videopoints(filename)
        
    except Exception as e:
        logging.getLogger(__name__).error(e, exc_info=True)
        sys.exit(1)
