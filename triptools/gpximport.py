#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import calendar
import gpxpy
import logging
import os
import sys

from triptools import config
from triptools import Trackpoint
from triptools import DB
from triptools.common import get_names

logging.basicConfig(level=logging.INFO)

def import_gpxtrack(db, filename):
    with db.getconn() as conn:
        with open(filename, "r", encoding="utf8") as gpx_file:
            count = 0
            records = gpxpy.parse(gpx_file)
            for tp in records.walk(True):
                t = Trackpoint(calendar.timegm(tp.time.utctimetuple()),
                               tp.longitude,
                               tp.latitude,
                               tp.elevation)
                count += db.add_trackpoint(conn, t)
            logging.getLogger(__name__).info("file '%s' imported, %d trackpoints added to DB" % (filename, count))
            
if __name__ == "__main__":

    db = DB()
    
    for filename in get_names(config.get("GPX", "name"), config.get("GPX", "mask")):
        try:
            if not os.access(filename, os.R_OK):
                raise Exception("cannot read gpx file '%s'" % filename)
            import_gpxtrack(db, filename)
        except Exception as e:
            logging.getLogger(__name__).error(e)

        
