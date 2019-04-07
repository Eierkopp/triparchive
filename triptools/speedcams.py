#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import gzip
import logging
import os
import shlex
import subprocess
import sys

import overpy
from triptools import config

logging.basicConfig(level=logging.INFO)

sp_conf = config["Speedcams"]

def download():
    api = overpy.Overpass()
    r = api.query("""
<osm-script timeout="900" element-limit="1073741824">
  <query type="relation">
    <has-kv k="type" v="enforcement"/>
  </query>
  <recurse type="relation-node"/>
  <print/>
</osm-script>""")
    return r
    
def get_proximity(speed):
    return int(speed * 30 / 3.6) # 30 seconds

def get_details(data):
    FILTER_TAG='highway'
    for n in data.get_nodes():
        if FILTER_TAG not in n.tags:
            continue
        lat, lon = float(n.lat), float(n.lon)
        ft = n.tags[FILTER_TAG]
        try:
            speed_txt = n.tags["maxspeed"].split()
            speed = float(speed_txt[0])
            if len(speed_txt) > 1 and speed_txt[1] == "mph":
                speed *= 1.609
            proximity = get_proximity(speed)
            speed = "%dkm/h" % int(speed)
        except:
            # unknown or variable speed
            speed = "5km/h"
            proximity = get_proximity(50)
            
        yield lon, lat, ft, speed, proximity
            
def export(data):
    poi_file = sp_conf["poi_file"]
    missing_translation = set()
    default_ft = sp_conf.get("default_feature")
    
    args = [config.get("Tools", "gpsbabel_path")] + shlex.split("-i unicsv -f - -o garmin_gpi,alerts=1 -F") + [poi_file]
    
    with subprocess.Popen(args, stdin=subprocess.PIPE) as gpsbabel:
        gpsbabel.stdin.write(b"No,Latitude,Longitude,Name,Symbol,Proximity\n")
        count=1
        for lon, lat, ft, max_speed, proximity in get_details(data):
            ft_key = ("translation_" + ft).replace(" ", "")
            if ft_key not in sp_conf and ft_key not in missing_translation:
                logging.getLogger(__name__).warn("no translation for %s" % ft_key)
                missing_translation.add(ft_key)
                
            feature = "%s-%d" % (sp_conf.get(ft_key, default_ft), count)
            speed_ind = "@%s" % max_speed if max_speed else ""
            line = '%d,%f,%f,%s%s,"Waypoint",%d\n' % (count, lat, lon, feature, speed_ind,  proximity)
            gpsbabel.stdin.write(line.encode("utf8"))
            count += 1

    logging.getLogger(__name__).info("osm speedcams written to %s" % poi_file)
        
            
if __name__ == "__main__":

    try:
        if not os.access(config.get("Tools", "gpsbabel_path"), os.X_OK):
            raise Exception("gpsbabel missing or gpsbabel_path misconfigured")
    
        data = download()
        export(data)

    except Exception as e:
        logging.getLogger(__name__).error(e, exc_info=True)
        sys.exit(1)
