#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import logging
import os
import sys
import cairocffi as cairo
from imageio.plugins import ffmpeg
from moviepy.editor import CompositeVideoClip, VideoFileClip
import math
import shutil
import subprocess
import tempfile
import time

from triptools import config
from triptools import DB
from triptools import osm_mapper
from triptools.common import Track, Trackpoint

logging.basicConfig(level=logging.INFO)

def cairoArrow(tipX, tailX, tipY, tailY, ctx):

    ctx.move_to(tipX, tipY)
    
    dx = tipX - tailX;
    dy = tipY - tailY;
    arrowLength = math.sqrt(dx*dx + dy * dy) / 2

    theta = math.atan2(dy, dx)

    rad = math.radians(35)
    x = tipX - arrowLength * math.cos(theta + rad)
    y = tipY - arrowLength * math.sin(theta + rad)

    ctx.line_to(x, y)

    phi2 = math.radians(-35)
    x2 = tipX - arrowLength * math.cos(theta + phi2)
    y2 = tipY - arrowLength * math.sin(theta + phi2)

    ctx.line_to(x2, y2)
    
    ctx.close_path()

    ctx.fill()

def makeMaps(filename, track, start_time, duration):

    MAP_FORMAT = "map%05d.png"
    
    framerate = config.getint("Video", "map_framerate")
    width = config.getint("Video", "map_width")
    height = config.getint("Video", "map_height")
    zoom = config.getint("Video", "map_zoom")
    
    dir_name = tempfile.mkdtemp(prefix="mapmovie_")
    map_movie_name = tempfile.mktemp(prefix="mapmovie_", suffix=".mp4")

    t = start_time
    n = 0
    db = DB()
    
    while t < start_time + duration:
        print("%s -> %s" % (time.ctime(t), track.get(t)))

        tp = track.get(t)
        
        _, image = osm_mapper.get_centered_map(tp.longitude,
                                               tp.latitude,
                                               zoom,
                                               (width, height))

        # cairo code
        surface = osm_mapper.as_surface(image)
        cr = cairo.Context(surface)

        # nearest Place
        
        feature = db.get_nearest_feature(tp, features=["S", "P"])
        if feature:
            cr.select_font_face("Courier");
            cr.move_to(10,70)
            cr.set_source_rgb(0, 0, 0) # black
            cr.set_font_size(17.0)
            cr.show_text(feature.name)
                        
        # speed indication
        cr.select_font_face("Courier");
        cr.move_to(10,30)
        cr.set_source_rgb(0, 0, 0) # black
        cr.set_font_size(17.0)
        cr.show_text("%6.1fkm/h" % track.speed(t))

        # altitude
        cr.move_to(10,50)
        cr.set_source_rgb(0, 0, 0) # black
        cr.set_font_size(17.0)
        cr.show_text("%6.1füNN" % tp.altitude)

        # direction indication
        cr.move_to(width/2, height/2)
        cr.set_line_width(2)
        bearing_lon, bearing_lat = track.bearing(t)
        cr.line_to(width/2 + bearing_lon, height/2 - bearing_lat)
        cr.stroke()
        cairoArrow(width/2 + bearing_lon, width/2, height/2 - bearing_lat, height/2, cr)
            
        surface.write_to_png(os.path.join(dir_name, MAP_FORMAT % n))
        
        n += 1
        t += 1.0 / framerate

    rc = subprocess.call([ffmpeg.get_exe(), "-framerate", str(framerate),
                          "-i", os.path.join(dir_name, MAP_FORMAT),
                          "-c:v", "libx264",
                          "-r", "30", "-pix_fmt", "yuv420p", map_movie_name])

    shutil.rmtree(dir_name)
    
    if rc != 0:
        raise Exception("Failed to create maps movie %s" % map_movie_name)

    return map_movie_name
  
            
def renderOverlay(filename, maps_movie, target_name):
    cam_clip = VideoFileClip(filename)
    map_clip = VideoFileClip(maps_movie).set_opacity(0.7)

    video = CompositeVideoClip([cam_clip,
                                map_clip.set_pos(("right","top"))])

    video.write_videofile(target_name,
                          fps=cam_clip.fps,
                          codec="h264",
                          audio_codec="mp3",
                          #temp_audiofile="xx.aac",
                          bitrate="8000K")

    os.remove(maps_movie)

if __name__ == "__main__":

    try:
        filename = config.get("Video", "name")
        filename = os.path.abspath(filename)
        with DB() as db:
            video_info = db.get_video(filename)
            if video_info is None:
                raise Exception("Video needs to be imported first")
            video_id = str(video_info["_id"])
            start_time = video_info["start_time"]
            duration = video_info["duration"]

            if config.getboolean("Video", "use_camera_track"):
                track_points = db.fetch_videopoints(video_id)
            else:
                track_points = db.fetch_trackpoints(start_time, start_time + duration)
            track = Track(track_points)
            
            maps_movie = makeMaps(filename, track, start_time, duration)

            renderOverlay(filename, maps_movie, "/tmp/xx.mp4")
            
    except Exception as e:
        logging.getLogger(__name__).error(e, exc_info=True)
        sys.exit(1)
