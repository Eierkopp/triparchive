#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import dateutil.parser as parser
import calendar
import logging
import sys

from triptools import config
from triptools import DB
from triptools import osm_mapper

logging.basicConfig(level=logging.INFO)

def parse_ts(ts):
    """Convert a timestamp into a time_t"""
    dt = parser.parse(ts)
    return calendar.timegm(dt.utctimetuple())

def make_trackmap(start_time, end_time):
    db = DB()
    
    track = db.fetch_trackpoints(start_time, end_time)
    bb = osm_mapper.get_bounding_box(track,
                                     config.getfloat("Map", "marg_pct"),
                                     config.getfloat("Map", "marg_km"))

    map_tile, image = osm_mapper.get_map_from_bb(bb,
                                                 (config.getint("Map", "width"),
                                                  config.getint("Map", "height")))
    surface = osm_mapper.as_surface(image)
    osm_mapper.draw_trackpoints(map_tile, surface, track)
    surface.write_to_png(config.get("Map", "target"))
    
if __name__ == "__main__":

    try:

        start_time = parse_ts(config.get("Track", "start"))
        end_time = parse_ts(config.get("Track", "end"))
        
        make_trackmap(start_time, end_time)
        
    except Exception as e:
        logging.getLogger(__name__).error(e, exc_info=True)
        sys.exit(1)
