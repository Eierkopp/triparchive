#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from functools import lru_cache
import logging
import mimetypes
import os
import re
import sys

from flask import Flask, request, Response, redirect, render_template, make_response, send_file
from werkzeug.routing import FloatConverter as BaseFloatConverter

from triptools import config
from triptools import DB
from triptools import osm_mapper
from triptools.common import Track, Trackpoint, distance
from triptools.configuration import MOVIE_PROFILE_PREFIX

logging.basicConfig(level=logging.INFO)

def setup_app():
  
    class FloatConverter(BaseFloatConverter):
        regex = r'-?\d+(\.\d+)?'

    web_conf = config["Webserver"]
    app = Flask(__name__,
                static_folder=web_conf["static_dir"],
                template_folder=web_conf["templates_dir"])
    app.config['DEBUG'] = web_conf.getboolean("debug")
    app.url_map.converters['float'] = FloatConverter
    return app

SIZE = None
name_mask = None
db = None
videos = None
track_points = None

app = setup_app()
@app.after_request
def after_request(response):
    response.headers.add('Accept-Ranges', 'bytes')
    return response

def part(lon, lat, zoom):
    return "/%f/%f/%d" % (lon, lat, zoom)

@lru_cache(maxsize=1024)
def get_rendered_png(lon, lat, zoom):
    if zoom < 0:
        bb = osm_mapper.get_bounding_box(track_points,
                                         config.getfloat("Map", "marg_pct"),
                                         config.getfloat("Map", "marg_km"))
        map_tile, image = osm_mapper.get_map_from_bb(bb, SIZE)
    else:
        map_tile, image = osm_mapper.get_centered_map(lon, lat, zoom, SIZE)
    surface = osm_mapper.as_surface(image)
    osm_mapper.draw_trackpoints(map_tile, surface, track_points)
    data = surface.write_to_png()

    return map_tile, data

@app.route('/', defaults={"lon" : 0.0, "lat" : 0, "zoom" : -1})
@app.route('/<float:lon>/<float:lat>/<int:zoom>')
def root(lon, lat, zoom):
    map_tile, _ = get_rendered_png(lon, lat, zoom)
    lon1, lat1, lon2, lat2 = map_tile.extent
    lon, lat = map_tile.geocode((int(SIZE[0]/2), int(SIZE[1]/2)))
    zoom = map_tile.zoom
    h_step = (lon2 - lon1) / 3.0
    v_step = (lat2 - lat1) / 3.0
    return render_template("main.jinja2",
                           part=part(lon, lat, zoom),
                           up=part(lon, lat + v_step, zoom),
                           down=part(lon, lat - v_step, zoom),
                           left=part(lon - h_step, lat, zoom),
                           right=part(lon + h_step, lat, zoom),
                           zoom_in=part(lon, lat, zoom + 1),
                           zoom_out=part(lon, lat, zoom -1))

@app.route("/<float:lon>/<float:lat>/<int:zoom>/map.png")
def map(lon, lat, zoom):
    map_tile, data = get_rendered_png(lon, lat, zoom)
    resp = make_response(data, 200, { "content-type" : "image/png" })
    return resp

def get_video(id):
    for video in videos:
        if str(video["_id"]) == id:
            return video
    raise Exception("Invalid video id '%s'" % id)

@app.route('/play/<float:lon>/<float:lat>/<int:zoom>', methods=["POST"])
def play(lon, lat, zoom):

    def get_closest(lon, lat):
        best = track_points[0]
        best_dist = distance(lon, lat, best.longitude, best.latitude)
        for idx in range(1, len(track_points)):
            tp = track_points[idx]
            new_dist = distance(lon, lat, tp.longitude, tp.latitude)
            if new_dist < best_dist:
                best = tp
                best_dist = new_dist
        video = get_video(best.video_id)
        return video, best.timestamp, best.timestamp - video["start_time"]
    
    x = int(request.form["img.x"])
    y = int(request.form["img.y"])
    map_tile, data = get_rendered_png(lon, lat, zoom)
    lon, lat = map_tile.geocode((x,y))
    video, timestamp, offset = get_closest(lon, lat)
    fname = video["filename"]
    name, ext = os.path.splitext(fname)
    return redirect("sendvid/" + str(video["_id"]) + "/%d/vid" % offset + ext + "#t=%d" % offset, code=302)

def check_map(filename):
    base, _ = os.path.splitext(filename)
    for section in config.sections():
        if section.startswith(MOVIE_PROFILE_PREFIX):
            map_name = base + config.get(section, "name_suffix")
            if os.access(map_name, os.R_OK):
                return map_name
    return filename

@app.route("/sendvid/<id>/<int:offset>/<path:path>", methods=["GET"])
def sendvid(id, offset, path=None):
    video = get_video(id)
    filename = check_map(video["filename"])
    range_header = request.headers.get('Range', None)

    if not range_header:
        return send_file(filename)

    size = os.path.getsize(filename)    
    byte1, byte2 = 0, None
    
    m = re.search('(\d+)-(\d*)', range_header)
    g = m.groups()
    
    if g[0]: byte1 = int(g[0])
    if g[1]: byte2 = int(g[1])

    length = size - byte1
    if byte2 is not None:
        length = min(byte2 - byte1 + 1, length)
    if length > 10*1024*1024:
        length = config.getint("Webserver", "chunk_size")
    
    data = None
    with open(filename, 'rb') as f:
        f.seek(byte1)
        data = f.read(length)

    rv = Response(data, 
        206,
        mimetype=mimetypes.guess_type(path)[0], 
        direct_passthrough=True)
    rv.headers.add('Content-Range', 'bytes {0}-{1}/{2}'.format(byte1, byte1 + length - 1, size))

    return rv
    

if __name__ == "__main__":

    try:
        SIZE = (config.getint("Webserver", "map_width"),
                config.getint("Webserver", "map_height"))
        name_mask = config.get("Video", "mask")
        with DB() as db:
            video_ids = db.get_video_ids(name_mask)
            videos = [ db.get_video_by_id(id) for id in video_ids]
            track_points = db.fetch_videopoints(video_ids)
            app.run(host=config.get("Webserver", "interface"),
                    port=config.getint("Webserver", "port"),
                    debug=config.getboolean("Webserver", "debug"))
            
    except Exception as e:
        logging.getLogger(__name__).error(e, exc_info=True)
        sys.exit(1)

