#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import calendar
from datetime import datetime
import piexif
import pytz
import logging
import sys

from triptools import config
from triptools import DB
from triptools.common import Trackpoint, tp_dist

logging.basicConfig(level=logging.INFO)

def get_create_date(filename):
    """Fetch Date/Time Original and convert to time_t"""
    tz = pytz.timezone(config.get("Photo", "timezone"))
    exif = piexif.load(filename)
    try:
        ts = exif["Exif"][piexif.ExifIFD.DateTimeOriginal].decode("ascii")
        dt = datetime.strptime(ts, '%Y:%m:%d %H:%M:%S').replace(tzinfo=tz)
        time_t = calendar.timegm(dt.utctimetuple())
        return time_t
    except:
        raise Exception("Failed to extract Date/Time Original")

def get_trackpoint(timestamp):
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

    db = DB()
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

def get_loc_name(trackpoint):
    db = DB()
    features = db.get_features(trackpoint, config.getfloat("Photo", "max_feature_distance"))

if __name__ == "__main__":

    try:

        dto = get_create_date(config.get("Photo", "name"))
        location = get_trackpoint(dto)
        loc_name = get_loc_name(location)

    except Exception as e:
        logging.getLogger(__name__).error(e, exc_info=True)
        sys.exit(1)
