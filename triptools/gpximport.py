#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import calendar
import logging
import os
import sys
import xml.etree.ElementTree as ET
from dateutil.parser import parse as parse_ts

from triptools import config
from triptools import Trackpoint
from triptools import DB
from triptools.common import get_names

logging.basicConfig(level=logging.INFO)

def import_gpxtrack(db, filename):
    with db.getconn() as conn:
        with open(filename, "r", encoding="utf8") as gpx_file:
            count = 0
            doc = ET.parse(gpx_file)
            for ns in ["http://www.topografix.com/GPX/1/0", "http://www.topografix.com/GPX/1/1"]:
                trkpoints = doc.findall(".//{" + ns + "}trkpt")
                for tp in trkpoints:
                    ele_text = tp.find("{" + ns + "}ele")
                    if ele_text is None:
                        continue
                    elevation = [float(ele) for ele in ele_text.itertext()][0]
                    ts_text = tp.find("{" + ns + "}time")
                    if ts_text is None:
                        continue
                    timestamp = [parse_ts(ts) for ts in ts_text.itertext()][0]
                    t = Trackpoint(calendar.timegm(timestamp.utctimetuple()),
                                   tp.get("lon"),
                                   tp.get("lat"),
                                   elevation)
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
            logging.getLogger(__name__).error("Error in %s: %s", filename, e, exc_info=True)

        
