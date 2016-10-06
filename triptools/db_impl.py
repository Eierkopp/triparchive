from functools import lru_cache
import logging
import re
import sqlite3
import traceback
import types

from triptools import config
from triptools import Trackpoint

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
    "CREATE VIRTUAL TABLE IF NOT EXISTS videopoint_index using rtree (rowid, min_lon, max_lon, min_lat, max_lat)",
    "CREATE TRIGGER IF NOT EXISTS insert_videopoint_trg after insert on videopoints begin insert into videopoint_index values (NEW.rowid, NEW.longitude, NEW.latitude, NEW.longitude, NEW.latitude); end",
    "CREATE TRIGGER IF NOT EXISTS delete_videopoint_trg after delete on videopoints begin delete from videopoint_index where rowid = OLD.rowid; end"
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
            c.execute("insert into videopoints values (?,?,?,?)", (lon, lat, offset, video_id))

    def fetch_videopoints(self, video_ids):
        if isinstance(video_ids, int): video_ids = [ video_ids]
        track = []
        with self.conn() as db:
            for id in video_ids:
                with CWrap(db.execute("select * from videopoints where video_id = ?", (id,))) as c:
                    for row in c.cursor:
                        track.append(DB.from_videopoint(row))
        return track
