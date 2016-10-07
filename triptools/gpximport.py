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

logging.basicConfig(level=logging.INFO)

def import_gpxtrack(filename):

    with DB() as db:
        tps = db.trackpoints()
        with open(filename, "r", encoding="utf8") as gpx_file:
            count = 0
            records = gpxpy.parse(gpx_file)
            for tp in records.walk(True):
                t = Trackpoint(calendar.timegm(tp.time.utctimetuple()),
                               tp.longitude,
                               tp.latitude,
                               tp.elevation)
                count += db.add_trackpoint(tps, t)
            logging.getLogger(__name__).info("file '%s' imported, %d trackpoints added to DB" % (filename, count))
            
if __name__ == "__main__":

    try:
        filename = config.get("GPX", "name")
        if not os.access(filename, os.R_OK):
            raise Exception("cannot read gpx file '%s'" % filename)

        import_gpxtrack(filename)
        
    except Exception as e:
        logging.getLogger(__name__).error(e, exc_info=True)
        sys.exit(1)

        
