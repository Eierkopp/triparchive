#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import logging
import os
import re
import sys
from io import BytesIO
from PIL import Image

from triptools import config, DB
from triptools.common import Trackpoint, tp_dist, distance, get_names
from triptools.exif_support import get_location

logging.basicConfig(level=logging.INFO)

def get_thumbnail(filename):
    """Return PNG thumbnail as bytes object"""
    max_x = config.getint("Photo", "thumbwidth")
    max_y = config.getint("Photo", "thumbheight")
    im = Image.open(filename)
    x, y = im.size
    scale = max(x / max_x, y / max_y)
    im.thumbnail((int(x/scale), int(y/scale)), Image.ANTIALIAS)
    buffer = BytesIO()
    im.save(buffer, "PNG")
    buffer.seek(0)
    return buffer.read()

if __name__ == "__main__":

    with DB() as db:
        for filename in get_names(config.get("Photo", "name"), config.get("Photo", "mask")):
            try:
                logging.getLogger(__name__).info("Processing %s" % filename)
                if db.get_photo(filename) and not config.getboolean("Photo", "refresh"):
                    logging.getLogger(__name__).info("Photo %s already imported." % filename)
                    continue
                    
                location = get_location(filename)
                location.add("thumbnail", get_thumbnail(filename))
                if location:
                    if db.add_photo(location) == 1:
                        logging.getLogger(__name__).info("Photo %s added." % filename)

            except Exception as e:
                logging.getLogger(__name__).error(e)
