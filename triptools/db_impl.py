import logging
import re
import pymongo
from bson.objectid import ObjectId
import traceback
import types

from triptools import config
from triptools.common import Trackpoint, Feature, distance


logging.basicConfig(level=logging.INFO)

class DB:

    def __init__(self):
        self.host = config.get("DB", "host")
        self.port = config.get("DB", "port")
        self.db_name = config.get("DB", "database")
        self.__conn = pymongo.MongoClient("localhost", 27017)
        print("Open")

    def __enter__(self):
        return self

    def __exit__(self, type, value, tb):
        self.__conn.close()
        print("Closed")
        
    def trackpoints(self):
        return self.__setup_collection("trackpoints")

    def geonetnames(self):
        return self.__setup_collection("geonetnames")

    def videopoints(self):
        return self.__setup_collection("videopoints")

    def videos(self):
        return self.__setup_collection("videos")

    def geonetnames(self):
        return self.__setup_collection("geonetnames")

    def __setup_collection(self, coll_name):
        db = self.__conn.get_database(self.db_name)
        return db.get_collection(coll_name)
    
    #
    # trackpoints support
    #
                    
    @staticmethod
    def from_trackpoint(doc):
        return Trackpoint(doc["timestamp"],
                          doc["location"]["coordinates"][0],
                          doc["location"]["coordinates"][1],
                          doc["altitude"])

    def add_trackpoint(self, trackpoints, tp):
        try:
            trackpoints.insert({
                "timestamp" : tp.timestamp,
                "location" : { "type": "Point",
                               "coordinates": [ tp.longitude, tp.latitude ]
                },
                "altitude" : tp.altitude
            })
        except pymongo.errors.DuplicateKeyError:
            return 0
        return 1
            
    def fetch_trackpoints(self, start_ts, end_ts):
        trackpoints = self.trackpoints()
        with trackpoints.find({  "$and" : [ {"timestamp" : { "$gte" : start_ts}},
                                            {"timestamp" : { "$lte" : end_ts}} ]}).sort([("timestamp", pymongo.ASCENDING)]) as c:
            return [ DB.from_trackpoint(doc) for doc in c ]

    def fetch_closest_trackpoints(self, timestamp):
        trackpoints = self.trackpoints()
        try:
            with trackpoints.find({'timestamp' : { '$gte' : timestamp } }).sort([('timestamp', pymongo.ASCENDING)]).limit(1) as c:
                best_above = next(c)
        except StopIteration:
            best_above = None

        try:   
            with trackpoints.find({'timestamp' : { '$lt' : timestamp } }).sort([('timestamp', pymongo.DESCENDING)]).limit(1) as c:
                best_below = next(c)
        except StopIteration:
            best_below = None
            
        tp1 = DB.from_trackpoint(best_below) if best_below else None
        tp2 = DB.from_trackpoint(best_above) if best_above else None
        return tp1, tp2

    def get_track_from_rect(self, ll_corner, ur_corner):
        raise Exception("Foobared")
        with self.conn() as db:
            trackpoints = []
            with CWrap(db.execute("select timestamp from location_index where min_lon >= ? and min_lat >= ? and max_lon <= ? and max_lat <= ? order by timestamp", (ll_corner[0], ll_corner[1], ur_corner[0], ur_corner[1]))) as idx_cursor:
                for row in idx_cursor:
                    with CWrap(db.execute("select * from trackpoints where timestamp = ?", row)) as result:
                        trackpoints.append(DB.from_trackpoint(result.fetchone()))
        return trackpoints

    #
    # video support
    #

    @staticmethod
    def from_videopoint(doc):
        return Trackpoint(doc["offset"],
                          doc["location"]["coordinates"][0],
                          doc["location"]["coordinates"][1],
                          0.0)

    def get_video_id(self, filename):
        videos = self.videos()
        with videos.find({ "filename" : filename}) as cursor:
            ids = [ doc["_id"] for doc in cursor ]
        if ids:
            return str(ids[0])
        return str(videos.insert({"filename" : filename }))

    def get_video_ids(self, filemask):
        expr = re.compile(filemask)
        ids = []
        videos = self.videos()
        with videos.find() as cursor:
            for doc in cursor:
                if expr.search(doc["filename"]):
                    ids.append(str(doc["_id"]))
        return ids

    def remove_video(self, filename):
        videos = self.videos()
        videopoints = self.videopoints()
        with videos.find({ "filename" : filename}) as cursor:
            oids = [ doc["_id"] for doc in cursor ]
        for oid in oids:
            videopoints.remove({"video_id" : oid})
            videos.remove({"_id" : oid})

    def remove_points(self, video_id):
        videopoints = self.videopoints()
        videopoints.remove({"video_id" : ObjectId(video_id)})

    def add_video_point(self, lon, lat, offset, video_id):
        videopoints = self.videopoints()
        try:
            videopoints.insert({
                    "location" : { "type": "Point",
                                   "coordinates": [ lon, lat ]  
                                   },
                "video_id" : ObjectId(video_id),
                "offset" : offset,
            })
        except pymongo.errors.DuplicateKeyError:
            return 0
        return 1


    def fetch_videopoints(self, video_ids):
        if isinstance(video_ids, int): video_ids = [ video_ids]
        track = []
        videopoints = self.videopoints()
        for id in video_ids:
            with videopoints.find({"video_id" : ObjectId(id)}).sort([("offset", pymongo.ASCENDING)]) as c:
                track += [ DB.from_videopoint(row) for row in c]
        return track

    #
    # geonetnames support
    #

    @staticmethod
    def from_feature(doc):
        return Feature(doc["name"],
                       doc["location"]["coordinates"][0],
                       doc["location"]["coordinates"][1],
                       doc["feature"])
    
    def remove_gns(self, country):
        gns = self.geonetnames()
        gns.remove({ "country" : country})

    def add_gns(self, gns, country, lon, lat, name, feature):
        gns.insert({
            "location" : { "type": "Point",
                           "coordinates": [ lon, lat ] 
            },
            "feature" : feature,
            "name" : name,
            "country" : country
        })
        return 1

    def get_nearest_feature(self, tp, features=["P"]):
        gns = self.geonetnames()

        filter = {"location": {"$nearSphere":[ tp.longitude,
                                               tp.latitude ]}}
        
        if len(features) == 1:
            filter["feature"] = features[0]
        elif len(features) > 1:
            filter["$or"] = [ {"feature" : f} for f in features]

        try:
            with gns.find(filter).limit(1) as c:
                return DB.from_feature(next(c))
        except StopIteration:
            return None
        
                

def make_schema():
    with DB() as db:
        tps = db.trackpoints()
        tps.create_index([("timestamp", pymongo.ASCENDING)],
                         name="trackpoint_timestamp_idx", unique=True)

        videos = db.videos()
        videos.create_index([("filename", pymongo.ASCENDING)],
                            name="video_filename_idx", unique=True)

        videopoints = db.videopoints()
        videopoints.create_index([("video_id", pymongo.ASCENDING),
                                  ("offset", pymongo.ASCENDING)],
                                 name="videopoints_offset_video_idx", unique=True)

        gns = db.geonetnames()
        gns.create_index([("location", pymongo.GEOSPHERE)],
                          name="location_idx",unique=False, background=True)

make_schema()
