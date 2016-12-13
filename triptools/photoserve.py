#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import cairocffi as cairo
from functools import lru_cache
import logging
import math
import mimetypes
import os
import re
import sys

from flask import Flask, request, Response, redirect, render_template, make_response, send_file
from werkzeug.routing import FloatConverter as BaseFloatConverter
from gevent.wsgi import WSGIServer

from triptools import config
from triptools import DB
from triptools import osm_mapper
from triptools.common import Trackpoint, format_datetime

logging.basicConfig(level=logging.INFO)

def setup_app():
  
    class FloatConverter(BaseFloatConverter):
        """allow negative floats in URLs"""
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

app = setup_app()

def round_xy(lon, lat):
    def round_float(x):
        return int(x * 10000) / 10000
    return round_float(lon), round_float(lat)

def part(lon, lat, zoom):
    return "/%3.4f/%3.4f/%d" % (*round_xy(lon, lat), zoom)

def map_center(map_tile):
    return round_xy(*map_tile.geocode((int(SIZE[0]/2), int(SIZE[1]/2))))

@lru_cache(maxsize=1024)
def add_info(photo):
    photoconf = config["Photo"]
    photo.add("name", db.get_nearest_feature(photo).name)
    photo.add("ts_str", format_datetime(photo.timestamp, photoconf["comment_timestamp_format"], photoconf["img_timezone"]))

@lru_cache(maxsize=1024)
def get_photos(lon, lat, map_tile):
    lon1, lat1, lon2, lat2 = map_tile.extent
    photos = db.get_photos_bb(lon, lat, lon1, lat1, lon2, lat2, limit=100)
    for photo in photos:
        add_info(photo)
    return photos

@lru_cache(maxsize=1024)
def get_rendered_png(lon, lat, zoom):
    map_tile, image = osm_mapper.get_centered_map(lon, lat, zoom, SIZE)
    surface = osm_mapper.as_surface(image)
    photos = get_photos(*map_center(map_tile), map_tile)
    cr = cairo.Context(surface)
    cr.set_line_width(5)
    for p in photos:
        x, y = map_tile.rev_geocode( (p.longitude, p.latitude) )
        cr.move_to(x, y)
        cr.arc(x, y, 2, 0, 2 * math.pi)
    cr.stroke()
    data = surface.write_to_png()
    return map_tile, data

@app.route('/', defaults={"lon" : 7.0, "lat" : 50, "zoom" : 7})
@app.route('/<float:lon>/<float:lat>/<int:zoom>')
def root(lon, lat, zoom):
    map_tile, _ = get_rendered_png(lon, lat, zoom)
    lon1, lat1, lon2, lat2 = map_tile.extent
    lon, lat = map_center(map_tile)
    photos = get_photos(lon, lat, map_tile)
    zoom = map_tile.zoom
    h_step = (lon2 - lon1) / 3.0
    v_step = (lat2 - lat1) / 3.0
    return render_template("photos.jinja2",
                           enumerate=enumerate,
                           part=part(lon, lat, zoom),
                           up=part(lon, lat + v_step, zoom),
                           down=part(lon, lat - v_step, zoom),
                           left=part(lon - h_step, lat, zoom),
                           right=part(lon + h_step, lat, zoom),
                           zoom_in=part(lon, lat, zoom + 1),
                           zoom_out=part(lon, lat, zoom -1),
                           photos=photos)

@app.route('/zoom/<float:lon>/<float:lat>/<int:zoom>', methods=["GET", "POST"])
def zoom(lon, lat, zoom):
    x = int(request.form["img.x"])
    y = int(request.form["img.y"])
    map_tile, data = get_rendered_png(lon, lat, zoom)
    lon, lat = map_tile.geocode((x,y))
    return redirect(part(lon, lat, zoom+1), code=302)

@app.route('/view/<int:id>')
def view(id):
    photo = db.get_photo(id)
    add_info(photo)
    return render_template("photo.jinja2",
                           id=id,
                           size=SIZE,
                           name=photo.name)

@app.route('/v/<key>')
def v(key):
    photo = db.get_photo_by_hash(key)
    add_info(photo)
    return send_file(photo.filename)

@app.route('/sendimg/<int:id>')
def sendimg(id):
    photo = db.get_photo(id)
    return send_file(photo.filename)

@app.route('/sendthumb/<int:id>')
def sendthumb(id):
    photo = db.get_photo(id)
    return make_response(photo.thumbnail, 200, { "content-type" : "image/png" })

@app.route('/update/<float:lon>/<float:lat>/<int:zoom>')
def update(lon, lat, zoom):
    map_tile, data = get_rendered_png(lon, lat, zoom)
    lon, lat = map_tile.geocode((int(request.args["x"]), int(request.args["y"])))
    photos = get_photos(lon, lat, map_tile)
    return render_template("photo_list.jinja2",
                           enumerate=enumerate,
                           photos=photos)

@app.route("/<float:lon>/<float:lat>/<int:zoom>/map.png")
def map(lon, lat, zoom):
    map_tile, data = get_rendered_png(lon, lat, zoom)
    return make_response(data, 200, { "content-type" : "image/png" })

if __name__ == "__main__":

    try:
        SIZE = (config.getint("Webserver", "map_width"),
                config.getint("Webserver", "map_height"))

        with DB() as db:
            #            http_server = WSGIServer((config.get("Webserver", "interface"), config.getint("Webserver", "port")), app)
            #            http_server.serve_forever()

            app.run(host=config.get("Webserver", "interface"),
                    port=config.getint("Webserver", "port"))
            
    except Exception as e:
        logging.getLogger(__name__).error(e)
        sys.exit(1)

