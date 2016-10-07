#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import calendar
import gpxpy
import logging
import os
import shlex
import subprocess
import sys

from triptools import config
from triptools import Trackpoint
from triptools import DB

logging.basicConfig(level=logging.INFO)

def import_mtktrack():

    dev_name = config.get("MTK", "dev")
    if not os.access(dev_name, os.R_OK | os.W_OK):
        raise Exception("MTK device '%s' not accessible" % dev_name)

    args = [config.get("Tools", "gpsbabel_path")] + shlex.split("-i mtk -t -f %s -o gpx -F -" % dev_name)
    count = 0
    with subprocess.Popen(args, stdout=subprocess.PIPE) as gpsbabel:
        output, _ = gpsbabel.communicate()
    output = output.decode("ascii")
    records = gpxpy.parse(output)

    with DB() as db:
        trackpoints = db.trackpoints()
        for tp in records.walk(True):
            t = Trackpoint(calendar.timegm(tp.time.utctimetuple()),
                           tp.longitude,
                           tp.latitude,
                           tp.elevation)
            count += db.add_trackpoint(trackpoints, t)

    logging.getLogger(__name__).info("Trackpoints from '%s' imported, %d trackpoints added to DB" % (dev_name, count))
            
if __name__ == "__main__":

    try:
        if not os.access(config.get("Tools", "gpsbabel_path"), os.X_OK):
            raise Exception("gpsbabel missing or gpsbabel_path misconfigured")
        
        import_mtktrack()
        
    except Exception as e:
        logging.getLogger(__name__).error(e, exc_info=True)
        sys.exit(1)

        
