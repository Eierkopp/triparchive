#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import dateutil.parser as parser
import calendar
from datetime import datetime
import logging
import os
import sys
import time

from triptools import config, distance
from triptools import DB
from triptools import osm_mapper

logging.basicConfig(level=logging.INFO)

def parse_ts(ts):
    """Convert a timestamp into a time_t"""
    dt = parser.parse(ts)
    return calendar.timegm(dt.utctimetuple())

def write_track(track, track_name):
    with open(track_name, "w") as outf:
        outf.write("""<?xml version="1.0" encoding="UTF-8" standalone="no" ?>
    <gpx xmlns="http://www.topografix.com/GPX/1/1"
         creator="GPSWPT_to_GPX"
         version="1.1"
         xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
         xsi:schemaLocation="http://www.topografix.com/GPX/1/1 http://www.topografix.com/GPX/1/1/gpx.xsd">
    """)

        previous = None
        trackSegOpen = False
        count = 0
        for i in track:
            if (not previous
                or abs(previous.timestamp - i.timestamp) > 3600
                or distance(previous.longitude, previous.latitude,
                            i.longitude, i.latitude) > 5000.0):
                print("starting new track segment at", time.strftime("%d.%m.%Y,%H:%M", time.localtime(i.timestamp)))
                if trackSegOpen:
                    outf.write("    </trkseg>\n")
                    outf.write("  </trk>\n")
                outf.write("  <trk>\n")
                outf.write("    <name>%s_%02d</name>\n" % (os.path.splitext(os.path.basename(track_name))[0], count) )
                outf.write("    <trkseg>\n")
                trackSegOpen = True
                count += 1

            outf.write('      <trkpt lat="%f" lon="%f">\n        <ele>%f</ele>\n        <time>%s</time>\n      </trkpt>\n' % (i.latitude, i.longitude, i.altitude, datetime.utcfromtimestamp(i.timestamp).isoformat() + "Z") )
            previous = i

        if trackSegOpen:
            outf.write("    </trkseg>\n")
            outf.write("  </trk>\n")

        outf.write("</gpx>\n")

def make_trackmap(start_time, end_time, track_name):
    with DB() as db:
        track = db.fetch_trackpoints(start_time, end_time)
        if len(track)< 2:
            raise Exception("track too short")

        write_track(track, track_name)

        bb = osm_mapper.get_bounding_box(track,
                                         config.getfloat("Map", "marg_pct"),
                                         config.getfloat("Map", "marg_km"))

        map_tile, image = osm_mapper.get_map_from_bb(bb,
                                                     (config.getint("Map", "width"),
                                                      config.getint("Map", "height")))
        surface = osm_mapper.as_surface(image)
        osm_mapper.draw_trackpoints(map_tile, surface, track)
        target = config.get("Map", "target")
        surface.write_to_png(target)

        logging.getLogger(__name__).info("Trackmap with %d trackpoints written to %s", len(track), target)
    
if __name__ == "__main__":

    try:

        start_time = parse_ts(config.get("Track", "start"))
        end_time = parse_ts(config.get("Track", "end"))
        track_name = config.get("Track", "name")

        make_trackmap(start_time, end_time, track_name)
        
    except Exception as e:
        logging.getLogger(__name__).error(e, exc_info=True)
        sys.exit(1)
