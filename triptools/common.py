import math

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
