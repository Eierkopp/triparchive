#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from datetime import datetime
import logging
import os
import re
import shutil
import sys

from triptools import config
from triptools import DB
from triptools.common import Trackpoint, tp_dist, distance, format_datetime, get_names
from triptools.exif_support import get_create_date, add_location_and_name

logging.basicConfig(level=logging.INFO)

def get_trackpoint(db, timestamp):
    """Fetch last trackpoint recorded before and first trackpoint
    recorded after the image timestamp. If both points are closer than
    max_distance together, a linear interpolation is used. If not, the
    closer timestamp is used, if recorded at most max_time_diff before
    or after the image.
    """

    max_time = config.getfloat("Photo", "max_time_diff")
    max_dist = config.getfloat("Photo", "max_distance")

    def interp(a1, x1, a2, x2, x):
        if x1 == x2:
            return a1
        return a1 + (x - x1)*(a2 - a1)/(x2 - x1)

    tp1, tp2 = db.fetch_closest_trackpoints(timestamp)
    print(tp1, tp2)
    if tp1 and tp2 and tp_dist(tp1, tp2) < max_dist:
        return Trackpoint(timestamp,
                          interp(tp1.longitude, tp1.timestamp, tp2.longitude, tp2.timestamp, timestamp),
                          interp(tp1.latitude, tp1.timestamp, tp2.latitude, tp2.timestamp, timestamp),
                          interp(tp1.altitude, tp1.timestamp, tp2.altitude, tp2.timestamp, timestamp))

    tp = None
    if tp1 and timestamp - tp1.timestamp < max_time:
        tp = tp1
        tp.timestamp = timestamp

    if tp2 and tp2.timestamp - timestamp < max_time:
        if tp is None or timestamp - tp.timestamp > tp2.timestamp - timestamp:
            tp = tp2
            tp.timestamp = timestamp
    if tp:
        return tp
    
    raise Exception("No trackpoint found")

def get_loc_name(db, trackpoint):
    feature = db.get_nearest_feature(trackpoint, ["P", "S", "R"])
    if (feature is None
        or distance(trackpoint.longitude, trackpoint.latitude,
                    feature.longitude, feature.latitude) > config.getfloat("Photo", "max_feature_distance")):
        raise Exception("No location name found. Maybe a GNS file needs to be imported?")
    return feature.name

def rename(name, dto, location, loc_name):
    photoconf = config["Photo"]
    time_str = format_datetime(dto,
                               photoconf["img_timestamp_format"],
                               photoconf["img_timezone"])

    loc_str = loc_name.encode("ascii", "ignore").decode("ascii")
    
    new_name = photoconf["img_format"] % {"timestamp" : time_str,
                                          "location" : loc_str}
    target = os.path.join(os.path.dirname(name), new_name)
    if photoconf.getboolean("rename"):
        logging.getLogger(__name__).info("Renaming %s to %s", name, target)
        os.rename(name, target)
    else:
        logging.getLogger(__name__).info("Copying %s to %s", name, target)
        shutil.copyfile(name, target)
    return target

    
if __name__ == "__main__":

    with DB() as db:
        for filename in get_names(config.get("Photo", "name"), config.get("Photo", "mask")):
            try:
                logging.getLogger(__name__).info("Processing %s" % filename)
                dto = get_create_date(filename)
                location = get_trackpoint(db, dto)
                loc_name = get_loc_name(db, location)
                new_name = rename(filename, dto, location, loc_name)
                add_location_and_name(new_name, location, dto, loc_name)
            except Exception as e:
                logging.getLogger(__name__).error(e)
