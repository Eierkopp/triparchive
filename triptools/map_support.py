#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import asyncio
import redis
import geotiler
import cairocffi as cairo
from geotiler.cache import redis_downloader

from triptools.common import EARTH_RADIUS, dist_to_deg, tp_dist

class MapTool:

    def __init__(self, redis_host):
        client = redis.Redis(redis_host)
        self.downloader = redis_downloader(client, timeout=86400 * 356) # cache for 1 year
        
    @staticmethod
    def fix_async_io_event_loop():
        """create default event loop, required if run e.g. from flask"""
        try:
            event_loop = asyncio.get_event_loop()
        except:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

    @staticmethod
    def as_surface(image):
        buff = bytearray(image.convert('RGBA').tobytes('raw', 'BGRA'))
        return cairo.ImageSurface.create_for_data(buff, cairo.FORMAT_ARGB32, image.size[0], image.size[1])

    @staticmethod
    def get_bounding_box(track, margin_pct=0.1, margin_km=0.2):
        """Compute approximate bounding box"""

        def compute_margin(cmin, cmax, margin_pct, margin_km):
            margin = (cmax - cmin) * margin_pct
            margin_deg = dist_to_deg(margin_km * 1000)
            return max(margin, margin_deg)

        max_lon = min_lon = track[0].longitude
        max_lat = min_lat = track[0].latitude
        for t in track:
            if max_lon < t.longitude: max_lon = t.longitude
            if min_lon > t.longitude: min_lon = t.longitude
            if min_lat > t.latitude: min_lat = t.latitude
            if max_lat < t.latitude: max_lat = t.latitude

        marg_lon = compute_margin(min_lon, max_lon, margin_pct, margin_km)
        marg_lat = compute_margin(min_lat, max_lat, margin_pct, margin_km)
        return ( (min_lon - marg_lon, min_lat - marg_lat), (max_lon + marg_lon, max_lat + marg_lat) )

    def get_map_from_bb(self, bb, size):
        MapTool.fix_async_io_event_loop()
        lb,ru = bb
        map_tile = geotiler.Map(extent=(lb[0], lb[1], ru[0],ru[1]), size=size)
        image = geotiler.render_map(map_tile, downloader = self.downloader)
        return map_tile, image
        
    def get_centered_map(self, lon, lat, zoom, size):
        MapTool.fix_async_io_event_loop()
        map_tile = geotiler.Map(center=(lon, lat), zoom=zoom, size=size)
        image = geotiler.render_map(map_tile, downloader = self.downloader)
        return map_tile, image

    @staticmethod
    def draw_trackpoints(map_tile, surface, trackPoints):

        if not trackPoints:
            return

        # draw track
        cr = cairo.Context(surface)

        t = 0.0
        x1, y1 = map_tile.rev_geocode( (trackPoints[0].longitude, trackPoints[0].latitude) )
        tp = trackPoints[0]
        cr.move_to(x1, y1)
        cr.set_line_width(2)

        t = 1.0
        for t in trackPoints:

            x2, y2 = map_tile.rev_geocode( (t.longitude, t.latitude) )
            if tp_dist(tp, t) < 100:
                cr.line_to(x2, y2)
            else:
                cr.move_to(x2, y2)

            x1, y1 = x2, y2
            tp = t

        cr.stroke()
