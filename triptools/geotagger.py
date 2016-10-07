#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import calendar
from datetime import datetime
import piexif
import pytz
import logging
import os
import shutil
import sys

from triptools import config
from triptools import DB
from triptools.common import Trackpoint, tp_dist, distance

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
    fileTZ = pytz.timezone(photoconf["img_timezone"])
    timestamp = datetime.fromtimestamp(dto, tz=fileTZ)
    time_str = timestamp.strftime(photoconf["img_timestamp_format"])

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

def make_fraction(value, denom):
    return int(value * denom), denom

def make_triplet(value):
    """create a vector of three rationals for value, minutes and seconds"""
    value = abs(value)
    degrees = int(value)
    value = 60*(value-degrees)
    minutes = int(value)
    seconds = 60 * (value - minutes)
    return [ make_fraction(degrees,10), make_fraction(minutes, 10), make_fraction(seconds, 100)]
    
def add_tags(new_name, location, dto, loc_name):
    photoconf = config["Photo"]
    fileTZ = pytz.timezone(photoconf["img_timezone"])
    timestamp = datetime.fromtimestamp(dto, tz=fileTZ)
    time_str = timestamp.strftime(photoconf["comment_timestamp_format"])
    comment = photoconf["comment_format"] % {"timestamp" : time_str,
                                             "location" : loc_name}
    import codecs
    exif = piexif.load(new_name)
    exif["0th"][piexif.ImageIFD.ImageDescription] = comment.encode("ascii", "ignore")
    exif["Exif"][piexif.ExifIFD.UserComment] = "UNICODE\0".encode("ascii") + comment.encode("utf16")
    exif["GPS"][piexif.GPSIFD.GPSVersionID] = 2
    exif["GPS"][piexif.GPSIFD.GPSAltitude] = make_fraction(location.altitude, 10)
    exif["GPS"][piexif.GPSIFD.GPSAltitudeRef] = 0 if location.altitude >= 0 else 1
    exif["GPS"][piexif.GPSIFD.GPSLongitude] = make_triplet(location.longitude)
    exif["GPS"][piexif.GPSIFD.GPSLongitudeRef] = 'E' if location.longitude >= 0 else 'W'
    exif["GPS"][piexif.GPSIFD.GPSLatitude] = make_triplet(location.latitude)
    exif["GPS"][piexif.GPSIFD.GPSLatitudeRef] = 'N' if location.latitude >= 0 else 'S'

    piexif.insert(piexif.dump(exif), new_name)

if __name__ == "__main__":

    try:
        with DB() as db:
            filename = config.get("Photo", "name")
            dto = get_create_date(filename)
            location = get_trackpoint(db, dto)
            loc_name = get_loc_name(db, location)
            new_name = rename(filename, dto, location, loc_name)
            add_tags(new_name, location, dto, loc_name)

    except Exception as e:
        logging.getLogger(__name__).error(e, exc_info=True)
        sys.exit(1)
