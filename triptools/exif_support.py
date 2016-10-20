import codecs
import logging
import piexif

from triptools import config
from triptools.common import Trackpoint, parse_datetime, format_datetime

logging.basicConfig(level=logging.INFO)

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

def get_create_date(filename, exif = None):
    """Fetch Date/Time Original and convert to time_t"""
    if exif is None:
        exif = piexif.load(filename)
    try:
        ts = exif["Exif"][piexif.ExifIFD.DateTimeOriginal].decode("ascii")
        return parse_datetime(ts, '%Y:%m:%d %H:%M:%S', config.get("Photo", "timezone"))
    except:
        raise Exception("Failed to extract Date/Time Original")

def add_location_and_name(new_name, location, dto, loc_name):
    photoconf = config["Photo"]
    time_str = format_datetime(dto, photoconf["comment_timestamp_format"], photoconf["img_timezone"])
    comment = photoconf["comment_format"] % {"timestamp" : time_str,
                                             "location" : loc_name}
    
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

def from_fraction(fract, ref, sign):
    return (fract[0] / fract[1]) * (1 if ref == sign else -1)

def from_triplet(triplet, ref, sign):
    value = (from_fraction(triplet[0], ref, sign)
             + from_fraction(triplet[1], ref, sign)/60.0
             + from_fraction(triplet[2], ref, sign)/3600.0)
    return value
    
def get_location(filename):
    try:
        exif = piexif.load(filename)
        altitude = from_fraction(exif["GPS"][piexif.GPSIFD.GPSAltitude],
                                 exif["GPS"][piexif.GPSIFD.GPSAltitudeRef],
                                 0)
        longitude = from_triplet(exif["GPS"][piexif.GPSIFD.GPSLongitude],
                                 exif["GPS"][piexif.GPSIFD.GPSLongitudeRef],
                                 b'E')
        latitude = from_triplet(exif["GPS"][piexif.GPSIFD.GPSLatitude],
                                exif["GPS"][piexif.GPSIFD.GPSLatitudeRef],
                                b'N')
        timestamp = get_create_date(filename, exif)
        return Trackpoint(timestamp, longitude, latitude, altitude, filename=filename)
    except KeyError:
        logging.getLogger(__name__).info("No location information in %s." % filename)
    except:
        logging.getLogger(__name__).error("Failed to process %s" % filename)
    return None
        
