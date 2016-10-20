#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import logging
import os
import re
import sys

from triptools import config, DB
from triptools.common import Trackpoint, tp_dist, distance
from triptools.exif_support import get_location

logging.basicConfig(level=logging.INFO)

def get_names():
    name = os.path.abspath(config.get("Photo", "name"))
    if os.path.isdir(name):
        mask = re.compile(config.get("Photo", "mask"))
        
        for dirpath, dirnames, filenames in os.walk(name):
            for filename in filenames:
                if mask.match(filename):
                    yield os.path.join(dirpath, filename)
    else:
        yield name

if __name__ == "__main__":

    with DB() as db:
        for filename in get_names():
            try:
                logging.getLogger(__name__).info("Processing %s" % filename)
                if db.get_photo(filename):
                    logging.getLogger(__name__).info("Photo %s already imported." % filename)
                    
                location = get_location(filename)
                if location:
                    if db.add_photo(location) == 1:
                        logging.getLogger(__name__).info("Photo %s added." % filename)

            except Exception as e:
                logging.getLogger(__name__).error(e)
