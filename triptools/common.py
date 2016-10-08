import math
import numpy as np
from scipy.interpolate import splev, splrep

class Trackpoint:

    def __init__(self, timestamp, lon, lat, alt):
        self.timestamp = timestamp
        self.longitude = lon
        self.latitude = lat
        self.altitude = alt

    def __str__(self):
        return "(%d: lon:%f lat:%f alt:%f)" % (self.timestamp, self.longitude, self.latitude, self.altitude)

    def __repr__(self):
        return self.__str__()

class Track:
    """Track class that can interpolate/extrapolate and provide a first
    derivative, aka speed"""

    SPEED_AVG = 0.5 # average speed over 0.5 seconds
    
    def __init__(self, trackpoints):
        timestamps = np.array([ tp.timestamp for tp in trackpoints])
        self.lons = splrep(timestamps, np.array([ tp.longitude for tp in trackpoints]))
        self.lats = splrep(timestamps, np.array([ tp.latitude for tp in trackpoints]))
        self.alts = splrep(timestamps, np.array([ tp.altitude for tp in trackpoints]))

    def get(self, ts):
        return Trackpoint(ts, self.lon(ts), self.lat(ts), self.alt(ts))

    def lon(self, ts):
        return float(splev(ts, self.lons))

    def lat(self, ts):
        return float(splev(ts, self.lats))

    def alt(self, ts):
        return float(splev(ts, self.alts))

    def speed(self, ts):
        lon1 = self.lon(ts - Track.SPEED_AVG/2.0)
        lon2 = self.lon(ts + Track.SPEED_AVG/2.0)

        lat1 = self.lat(ts - Track.SPEED_AVG/2.0)
        lat2 = self.lat(ts + Track.SPEED_AVG/2.0)

        speed_meter_per_second = distance(lon1, lat1, lon2, lat2) / Track.SPEED_AVG

        return float(speed_meter_per_second * 3.6) # return km/h

    def bearing(self, ts):
        lon1 = self.lon(ts - Track.SPEED_AVG/2.0)
        lon2 = self.lon(ts + Track.SPEED_AVG/2.0)

        lat1 = self.lat(ts - Track.SPEED_AVG/2.0)
        lat2 = self.lat(ts + Track.SPEED_AVG/2.0)

        lon_delta = distance(lon1, lat1, lon2, lat1) / Track.SPEED_AVG
        if (lon2 < lon1): lon_delta *= -1
        lat_delta = distance(lon1, lat1, lon1, lat2) / Track.SPEED_AVG
        if (lat2 < lat1): lat_delta *= -1

        return lon_delta, lat_delta
    

class Feature:

    FeatureMapper = { 'A' : 'Administrative region',
                      'P' : 'Populated place',
                      'V' : 'Vegetation',
                      'L' : 'Locality or area',
                      'U' : 'Undersea',
                      'R' : 'Streets',
                      'T' : 'Hypsographic',
                      'H' : 'Hydrographic',
                      'S' : 'Spot'
    }

    def __init__(self, name, longitude, latitude, feature_type):
        self.longitude = longitude
        self.latitude = latitude
        self.name = name
        self.feature_type = feature_type

    def __str__(self):
        return "(%s: lon:%f lat:%f type:%s)" % (self.name, self.longitude, self.latitude, self.feature_type)

    def __repr__(self):
        return self.__str__()


# approx earth radius in m
EARTH_RADIUS=6371000.0

def distance(lon1, lat1, lon2, lat2):
    """Approx distance in meter"""
    rlat1 = math.pi * lat1 / 180
    rlon1 = math.pi * lon1 / 180
    rlat2 =  math.pi * lat2 / 180
    rlon2 = math.pi * lon2 / 180
    dlon = rlon2 - rlon1
    dlat = rlat2 - rlat1
    a =  math.pow(math.sin(dlat/2),2) + math.cos(rlat1)*math.cos(rlat2)*math.pow(math.sin(dlon/2),2)
    c = 2*math.atan2(math.sqrt(a), math.sqrt(1-a))
    return EARTH_RADIUS*c

def tp_dist(tp1, tp2):
    return distance(tp1.longitude, tp1.latitude, tp2.longitude, tp2.latitude)

def dist_to_deg(dist):
    return dist / EARTH_RADIUS * 57.29577951308232
