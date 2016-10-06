#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import logging
import sys

from triptools import config
from triptools import DB
from triptools import osm_mapper

logging.basicConfig(level=logging.INFO)

def make_videomap(mask):
    db = DB()
    video_ids = db.get_video_ids(mask)

    track = db.fetch_videopoints(video_ids)
    if len(track)< 2:
        raise Exception("track too short")
    
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
        name_mask = config.get("Video", "mask")
        make_videomap(name_mask)
        
    except Exception as e:
        logging.getLogger(__name__).error(e, exc_info=True)
        sys.exit(1)
