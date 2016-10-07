from functools import lru_cache
import logging
import re
import pymongo
import traceback
import types

from triptools import config
from triptools.common import Trackpoint, tp_dist, dist_to_deg, distance

INIT_CMDS = [
    # trackpoints table, index, and trigger to populate index
    "CREATE TABLE IF NOT EXISTS trackpoints (timestamp int primary key, longitude float, latitude float, altitude float)",
    "CREATE VIRTUAL TABLE IF NOT EXISTS trackpoint_index USING RTREE (timestamp, min_lon, max_lon, min_lat, max_lat)",
    "CREATE TRIGGER IF NOT EXISTS insert_trackpoint_trg after insert on trackpoints begin insert into trackpoint_index values (NEW.timestamp, NEW.longitude, NEW.latitude, NEW.longitude, NEW.latitude); end",
    "CREATE TRIGGER IF NOT EXISTS delete_trackpoint_trg after delete on trackpoints begin delete from trackpoint_index where timestamp = OLD.timestamp; end",
    
    # videos table and trigger to cascade deletes
    "CREATE TABLE IF NOT EXISTS videos (filename text primary key)",
    "CREATE TRIGGER IF NOT EXISTS delete_video_trg after delete on videos begin delete from videopoints where video_id = OLD.rowid; end",

    # videopoints table, index, and trigger to cascade insert and delete
    "CREATE TABLE IF NOT EXISTS videopoints (longitude float, latitude float, offset int, video_id int)",
    "CREATE UNIQUE INDEX IF NOT EXISTS vid_offset_idx ON videopoints (offset, video_id)",
    "CREATE VIRTUAL TABLE IF NOT EXISTS videopoint_index using rtree (row, min_lon, max_lon, min_lat, max_lat)",
    "CREATE TRIGGER IF NOT EXISTS insert_videopoint_trg after insert on videopoints begin insert into videopoint_index values (NEW.rowid, NEW.longitude, NEW.latitude, NEW.longitude, NEW.latitude); end",
    "CREATE TRIGGER IF NOT EXISTS delete_videopoint_trg after delete on videopoints begin delete from videopoint_index where row = OLD.rowid; end",

    # countries table trigger to cascade deletes
    "CREATE TABLE IF NOT EXISTS countries (country text primary key)",
    "CREATE TRIGGER IF NOT EXISTS delete_country_trg after delete on countries begin delete from geonetnames where country_id = OLD.rowid; end",
    
    # geonetnames table, index, and trigger to cascade insert and delete
    "CREATE TABLE IF NOT EXISTS geonetnames (longitude float, latitude float, name text, feature text, country_id int)",
    "CREATE VIRTUAL TABLE IF NOT EXISTS gns_index using rtree (row, min_lon, max_lon, min_lat, max_lat)",
    "CREATE TRIGGER IF NOT EXISTS insert_gns_trg after insert on geonetnames begin insert into gns_index values (NEW.rowid, NEW.longitude, NEW.latitude, NEW.longitude, NEW.latitude); end",
    "CREATE TRIGGER IF NOT EXISTS delete_gns_trg after delete on geonetnames begin delete from gns_index where row = OLD.rowid; end",
]

logging.basicConfig(level=logging.INFO)

class CWrap:
    """Wrapper for cursors to support the 'with' statement"""
    
    def __init__(self, cursor):
        self.cursor = cursor

    def __getattr__(self, attr_name):
        if hasattr(self.cursor, attr_name):
            return getattr(self.cursor, attr_name)
        
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.cursor.close()

class DB:

    def __init__(self):
        self.connect_str = config.get("DB", "connect_string")
        self.make_schema()

    def conn(self):
        return sqlite3.connect(self.connect_str)
        
    @lru_cache()
    def make_schema(self):
        with self.conn() as db:
            with CWrap(db.cursor()) as c:
                for cmd in INIT_CMDS:
                    c.execute(cmd)

    #
    # trackpoints support
    #
                    
    @staticmethod
    def from_trackpoint(row):
        return Trackpoint(row[0], row[1], row[2], row[3])

    def add_trackpoint(self, conn, trackpoint):
        with CWrap(conn.execute("insert OR IGNORE into trackpoints (timestamp, longitude, latitude, altitude) values (?,?,?,?)", (trackpoint.timestamp, trackpoint.longitude, trackpoint.latitude, trackpoint.altitude))) as c:
            return c.rowcount
            
    def fetch_trackpoints(self, start_ts, end_ts):
        track = []
        with self.conn() as db:
            with CWrap(db.execute("select * from trackpoints where timestamp >= ? and timestamp <= ?", (start_ts, end_ts))) as c:
                for row in c.cursor:
                    track.append(DB.from_trackpoint(row))
        return track

    def fetch_closest_trackpoints(self, timestamp):
        with self.conn() as db:
            with CWrap(db.cursor()) as c:
                c.execute("select * from trackpoints where timestamp <= ? order by timestamp desc limit 1", (timestamp,))
                row = c.fetchone()
                tp1 = DB.from_trackpoint(row) if row else None
                c.execute("select * from trackpoints where timestamp >= ? order by timestamp asc limit 1", (timestamp,))
                row = c.fetchone()
                tp2 = DB.from_trackpoint(row) if row else None
                return tp1, tp2

    def get_track_from_rect(self, ll_corner, ur_corner):
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
    def from_videopoint(row):
        return Trackpoint(row[2], row[0], row[1], 0.0)

    def get_video_id(self, filename):
        with self.conn() as db:
            with CWrap(db.cursor()) as c:
                c.execute("select rowid from videos where filename = ?", (filename,))
                rows = c.fetchall()
                if len(rows) == 1:
                    return rows[0][0]
                c.execute("insert into videos (filename) values (?)", (filename,))
                return c.lastrowid

    def get_video_ids(self, filemask):
        expr = re.compile(filemask)
        ids = []
        with self.conn() as db:
            with CWrap(db.execute("select rowid, filename from videos order by rowid")) as c:
                for id, name in c.cursor:
                    if expr.search(name):
                        ids.append(id)
        return ids

    def remove_video(self, filename):
        with self.conn() as db:
            with CWrap(db.cursor()) as c:
                c.execute("delete from videos where filename = ?", (filename,))

    def remove_points(self, video_id):
        with self.conn() as db:
            with CWrap(db.cursor()) as c:
                c.execute("delete from videopoints where video_id = ?", (video_id,))

    def add_video_point(self, conn, lon, lat, offset, video_id):
        with CWrap(conn.cursor()) as c:
            c.execute("insert or ignore into videopoints values (?,?,?,?)", (lon, lat, offset, video_id))
            return c.rowcount

    def fetch_videopoints(self, video_ids):
        if isinstance(video_ids, int): video_ids = [ video_ids]
        track = []
        with self.conn() as db:
            for id in video_ids:
                with CWrap(db.execute("select * from videopoints where video_id = ?", (id,))) as c:
                    for row in c.cursor:
                        track.append(DB.from_videopoint(row))
        return track

    #
    # geonetnames support
    #

    def get_country_id(self, country):
        country = country.lower()
        with self.conn() as db:
            with CWrap(db.cursor()) as c:
                c.execute("select rowid from countries where country = ?", (country,))
                rows = c.fetchall()
                if len(rows) == 1:
                    return rows[0][0]
                c.execute("insert into countries (country) values (?)", (country,))
                return c.lastrowid

    def remove_gns(self, country_id):
        with self.conn() as db:
            with CWrap(db.cursor()) as c:
                c.execute("delete from geonetnames where country_id = ?", (country_id,))

    def add_gns(self, conn, country_id, values):
        lon, lat, name, feature = values
        with CWrap(conn.cursor()) as c:
            c.execute("insert or ignore into geonetnames values (?,?,?,?,?)", (lon, lat, name, feature, country_id))
            return c.rowcount

    def get_features(self, tp, max_dist_m):
        offs_deg = dist_to_deg(max_dist_m)
        bb = (tp.longitude - offs_deg, tp.longitude + offs_deg, tp.latitude - offs_deg, tp.latitude + offs_deg)
        print(bb)
        with self.conn() as conn:
            with CWrap(conn.cursor()) as c:
                c.execute("select rowid from geonetnames where longitude >= ? and longitude <= ? limit 100",
                          (tp.longitude - offs_deg, tp.longitude + offs_deg))
# and max_lon >= ? and min_lat <= ? and max_lat >= ?", bb)
                rows = c.fetchall()
                for row in rows:
                    c.execute("select * from geonetnames where rowid=?", row)
                    lon, lat, name, feature, country_id = c.fetchone()
                    print(feature, lon, lat, distance(tp.longitude, tp.latitude, lon,lat))
                
