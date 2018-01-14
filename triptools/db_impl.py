#!/usr/bin/env python3
from functools import lru_cache
import hashlib
import json
import logging
import psycopg2
from psycopg2.pool import ThreadedConnectionPool
from psycopg2.extras import Json
import re
from types import MethodType

from triptools import config
from triptools.common import Trackpoint, Feature, distance

logging.basicConfig(level=logging.INFO)

class ConnWrap:
    """Wrapper for connections to support pool"""

    def __init__(self, pool, conn):
        self.pool = pool
        self.conn = conn

    def __getattr__(self, attr_name):
        if hasattr(self.conn, attr_name):
            return getattr(self.conn, attr_name)
        
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.conn.__exit__(exc_type, exc_val, exc_tb)
        self.pool.putconn(self.conn)

class DB:

    def __init__(self):
        db_conf = config["DB"]
        self.pool = ThreadedConnectionPool(5, 50,
                                           database=db_conf["database"],
                                           host=db_conf["host"],
                                           port=db_conf["port"],
                                           user=db_conf["user"],
                                           password=db_conf["password"])
        self.__make_schema()
        
    def __make_schema(self):
        with self.getconn() as conn:
            with conn.cursor() as c:
                # trackpoints
                c.execute("CREATE TABLE IF NOT EXISTS trackpoints (timepoint int8 PRIMARY KEY, location geography(Point,4326), altitude float)")
                
                # videos
                c.execute("CREATE TABLE IF NOT EXISTS videos (id SERIAL PRIMARY KEY, filename text, starttime int8, duration float )")
                c.execute("CREATE UNIQUE INDEX IF NOT EXISTS filename_ux ON videos (filename)")
                
                #videopoints
                c.execute("CREATE TABLE IF NOT EXISTS videopoints (video_id int references videos(id), timepoint int8, altitude float, location geography(Point,4326), PRIMARY KEY (video_id, timepoint))")
                c.execute("CREATE INDEX IF NOT EXISTS videopoints_location_idx ON videopoints USING GIST (location)")
                # photos
                c.execute("CREATE TABLE IF NOT EXISTS photos (filename text PRIMARY KEY, location geography(Point,4326), altitude float, timepoint int8, id serial, thumbnail bytea, hash text)")
                c.execute("CREATE INDEX IF NOT EXISTS photos_location_idx ON photos USING GIST (location)")
                c.execute("CREATE UNIQUE INDEX IF NOT EXISTS photos_id_ux ON photos (id)")
                c.execute("CREATE UNIQUE INDEX IF NOT EXISTS photos_hash_ux ON photos (hash)")
                
                # geonetnames
                c.execute("CREATE TABLE IF NOT EXISTS geonetnames (name text, location geography(Point,4326), feature text, country text)")
                c.execute("CREATE INDEX IF NOT EXISTS geonetnames_location_idx ON geonetnames USING GIST (location)")

    def __enter__(self):
        return self
                
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.pool.closeall()

    def getconn(self):
        conn = self.pool.getconn()
        return ConnWrap(self.pool, conn)

    #
    # trackpoints support
    #
 
    @staticmethod
    def from_trackpoint(row):
        return Trackpoint(row[0], row[1], row[2], row[3])

    def add_trackpoint(self, conn, tp):
        with conn.cursor() as c:
            c.execute("INSERT INTO trackpoints (timepoint, location, altitude) VALUES (%(ts)s, ST_SetSRID(ST_Point(%(lon)s, %(lat)s),4326), %(alt)s) ON CONFLICT (timepoint) DO UPDATE SET location = ST_SetSRID(ST_Point(%(lon)s, %(lat)s),4326), altitude=%(alt)s",
                      { "ts" : tp.timestamp,
                        "lon" : tp.longitude,
                        "lat" : tp.latitude,
                        "alt" : tp.altitude})
            return c.rowcount
            
    def fetch_trackpoints(self, start_ts, end_ts):
        with self.getconn() as conn:
            with conn.cursor() as c:
                c.execute("SELECT timepoint, ST_X(location::geometry), ST_Y(location::geometry), altitude FROM trackpoints "
                          "WHERE timepoint >= %s AND timepoint <= %s ORDER BY timepoint ASC",
                          (start_ts, end_ts))
                result = []
                for row in c:
                    result.append(DB.from_trackpoint(row))
                return result

    def fetch_closest_trackpoints(self, timestamp):
        with self.getconn() as conn:
            with conn.cursor() as c:
                try:
                    c.execute("select timepoint, ST_X(location::geometry), ST_Y(location::geometry), altitude from trackpoints where timepoint >= %s order by timepoint asc limit 1", (timestamp,))
                    best_above = next(c)
                except StopIteration:
                    best_above = None

                try:   
                    c.execute("select timepoint, ST_X(location::geometry), ST_Y(location::geometry), altitude from trackpoints where timepoint < %s order by timepoint desc limit 1", (timestamp,))
                    best_below = next(c)
                except StopIteration:
                    best_below = None
            
        tp1 = DB.from_trackpoint(best_below) if best_below else None
        tp2 = DB.from_trackpoint(best_above) if best_above else None
        return tp1, tp2
    
    #
    # video support
    #

    @staticmethod
    def from_videopoint(row):
        return Trackpoint(row[0],
                          row[1],
                          row[2],
                          row[3],
                          video_id = row[4])
        
    def get_video_id(self, filename, starttime=None, duration=None):
        result = None
        with self.getconn() as conn:
            with conn.cursor() as c:
                if starttime and duration:
                    c.execute("insert into videos (filename, starttime, duration) values (%s, %s, %s) on conflict (filename) do update set starttime = %s, duration = %s returning id", (filename, starttime, duration, starttime, duration))
                    rows = c.fetchall()
                    result = rows[0][0]
                else:
                    c.execute("select id from videos where filename = %s", (filename,))
                    rows = c.fetchall()
                    result = rows[0][0]
                    
        return result

    def get_video(self, filename):
        try:
            with self.getconn() as conn:
                with conn.cursor() as c:
                    c.execute("select id, filename, starttime, duration from videos where filename = %s", (filename,))
                    row = next(c)
                    return { "id" : row[0],
                             "filename" : row[1],
                             "starttime" : row[2],
                             "duration" : row[3] }
        except StopIteration:
            return None                  

    def get_video_by_id(self, id):
        try:
            with self.getconn() as conn:
                with conn.cursor() as c:
                    c.execute("select id, filename, starttime, duration from videos where id = %s", (id,))
                    row = next(c)
                    return { "id" : row[0],
                             "filename" : row[1],
                             "starttime" : row[2],
                             "duration" : row[3] }
        except StopIteration:
            return None

    def get_video_ids(self, filemask):
        expr = re.compile(filemask)
        ids = []
        with self.getconn() as conn:
            with conn.cursor() as c:
                c.execute("select id, filename from videos")
                for vid, filename in c:
                    if expr.search(filename):
                        ids.append(vid)
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
        with self.getconn() as conn:
            with conn.cursor() as c:
                c.execute("delete from videopoints where video_id = %s", (video_id,))
                return c.rowcount

    def add_video_point(self, conn, lon, lat, alt, timepoint, video_id):
        with conn.cursor() as c:
            c.execute("insert into videopoints (video_id, timepoint, altitude, location) "
                      "values (%s,%s,%s,ST_SetSRID(ST_Point(%s, %s),4326))",
                      (video_id, timepoint, alt, lon, lat))
            return c.rowcount

    def fetch_videopoints(self, video_ids):
        if isinstance(video_ids, str): video_ids = [ video_ids]
        track = []
        with self.getconn() as conn:
            with conn.cursor() as c:
                c.execute("select timepoint, ST_X(location::geometry), ST_Y(location::geometry), altitude, video_id from videopoints where video_id in ('" + "','".join(map(str, video_ids)) + "') order by video_id, timepoint")
                track += [ DB.from_videopoint(row) for row in c]
        return track
    
    #
    # photo support
    #

    @staticmethod
    def from_photo(row):
        return Trackpoint(row[0],
                          row[1],
                          row[2],
                          row[3],
                          filename=row[4],
                          thumbnail=bytes(row[5]) if row[5] else None,
                          id=row[6])

    def add_photo(self, tp):
        with self.getconn() as conn:
            with conn.cursor() as c:
                c.execute("INSERT INTO photos (filename, location, altitude, timepoint, thumbnail, hash) VALUES (%(filename)s, ST_SetSRID(ST_Point(%(lon)s, %(lat)s),4326), %(alt)s, %(ts)s, %(thumbnail)s, %(hash)s) ON CONFLICT (filename) DO UPDATE SET location = ST_SetSRID(ST_Point(%(lon)s, %(lat)s),4326), altitude=%(alt)s, timepoint=%(ts)s, thumbnail=%(thumbnail)s, hash=%(hash)s",
                { "filename" : tp.filename,
                  "lon" : tp.longitude,
                  "lat" : tp.latitude,
                  "alt" : tp.altitude,
                  "ts" : tp.timestamp,
                  "thumbnail" : tp.thumbnail,
                  "hash" : hashlib.md5(tp.filename.encode("utf8")).hexdigest()})
                return c.rowcount

    @lru_cache(maxsize=256)
    def get_photo(self, key):
        if isinstance(key, int):
            where = "WHERE id = %s"
        else:
            where = "WHERE filename = %s"
        try:
            with self.getconn() as conn:
                with conn.cursor() as c:
                    c.execute("SELECT timepoint, ST_X(location::geometry), ST_Y(location::geometry), altitude, filename, thumbnail, id FROM photos " + where, (key,))
                    return DB.from_photo(next(c))
        except StopIteration:
            return None

    @lru_cache(maxsize=256)
    def get_photo_by_hash(self, key):
        try:
            with self.getconn() as conn:
                with conn.cursor() as c:
                    c.execute("SELECT timepoint, ST_X(location::geometry), ST_Y(location::geometry), altitude, filename, thumbnail, id FROM photos WHERE hash = %s", (key,))
                    return DB.from_photo(next(c))
        except StopIteration:
            return None

    def get_photos_bb(self, sort_x, sort_y, min_x, min_y, max_x, max_y, limit = 10):
        with self.getconn() as conn:
            with conn.cursor() as c:
                c.execute("SELECT timepoint, ST_X(location::geometry), ST_Y(location::geometry), altitude, filename, thumbnail, id FROM photos "
                          "WHERE location && ST_MakeEnvelope(%s, %s, %s, %s, 4326) "
                          "ORDER BY location <-> ST_SetSRID(ST_Point(%s, %s), 4326) "
                          "LIMIT %s",
                          (min_x, min_y, max_x, max_y, sort_x, sort_y, limit))
                return [DB.from_photo(row) for row in c]

    def get_photos_at(self, center_x, center_y, limit = 10):
        with self.getconn() as conn:
            with conn.cursor() as c:
                c.execute("SELECT timepoint, ST_X(location::geometry), ST_Y(location::geometry), altitude, filename, thumbnail, id FROM photos "
                          "ORDER BY location <-> ST_SetSRID(ST_Point(%s, %s), 4326) "
                          "LIMIT %s",
                          (center_x, center_y, limit))
                return [DB.from_photo(row) for row in c]

    #
    # geonetnames support
    #
        
    @staticmethod
    def from_feature(row):
        return Feature(row[0],
                       row[1],
                       row[2],
                       row[3])
    
    def remove_gns(self, country):
        with self.getconn() as conn:
            with conn.cursor() as c:
                c.execute("delete from geonetnames where country = %s", (country,))
                return c.rowcount

    def add_gns(self, conn, country, lon, lat, name, feature):
        with conn.cursor() as c:
            c.execute("insert into geonetnames (location, name, country, feature) values (ST_SetSRID(ST_Point(%s, %s),4326), %s, %s, %s)",
                      (lon, lat, name, country, feature))
            return c.rowcount

    def get_nearest_feature(self, tp, features=["P"]):
        with self.getconn() as conn:
            feature_expr = "('" + "','".join(features) + "')"
            with conn.cursor() as c:
                c.execute("select name, ST_X(location::geometry), ST_Y(location::geometry), feature from geonetnames where feature in " + feature_expr + " order by location <-> ST_SetSRID(ST_Point(%s, %s), 4326) limit 1",
                          (tp.longitude, tp.latitude))
                return DB.from_feature(next(c))
        
if __name__ == "__main__":

    db = DB("postgresql://triparchive:triparchive@synology:5433/triparchive")

    tp1, tp2 = db.fetch_closest_trackpoints(1151769313)

    print(db.get_nearest_feature(tp1, ["P", "S"]))
    
    

                
                           
