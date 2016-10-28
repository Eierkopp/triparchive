#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import gzip
import logging
import os
import shlex
import subprocess
import sys
from urllib.request import urlopen
from triptools import config

logging.basicConfig(level=logging.INFO)

sp_conf = config["Speedcams"]

def download(url):
    response = urlopen(url)
    data = response.read()
#    with open("/tmp/data.out", "rb") as inf:
#        data = inf.read()
#    with open("/tmp/data.out", "wb") as outf:
#        outf.write(data)
    return gzip.decompress(data).decode("utf8")

def get_proximity(speed):
    return int(speed * 30 / 3.6) # 30 seconds

def parse_lines(fName):
    for line in data.splitlines():
        line = line.strip()
        if line.startswith("#") or line.startswith("lat\tlon"):
            continue

        parts = line.split("\t")
        result = [None]*5
        result[4] = 300

        result[0] = float(parts[1]) # lon
        result[1] = float(parts[0]) # lat
        if parts[2] in ["maxspeed", "speed_camera"]:
            if parts[3]:
                try:
                    if parts[3].endswith("mph"):
                        speed = float(parts[3].split()[0])
                        result[4] = get_proximity(speed)
                        result[3] = "%dkmh" % int(1.609 * speed)
                    else:
                        result[3] = "%dkmh" % int(parts[3])
                except:
                    result[3] = "5kmh" # variable or unknown speed
                    
        result[2] = parts[2]
        yield result
            
def export(data):
    poi_file = sp_conf["poi_file"]
    missing_translation = set()
    default_ft = sp_conf.get("default_feature")
    
    args = [config.get("Tools", "gpsbabel_path")] + shlex.split("-i unicsv -f - -o garmin_gpi,alerts=1 -F") + [poi_file]
    
    with subprocess.Popen(args, stdin=subprocess.PIPE) as gpsbabel:
        gpsbabel.stdin.write(b"No,Latitude,Longitude,Name,Symbol,Proximity\n")
        count=1
        for lon, lat, ft, max_speed, proximity in parse_lines(data):
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
    
        data = download(sp_conf["osm_url"])
        export(data)

    except Exception as e:
        logging.getLogger(__name__).error(e, exc_info=True)
        sys.exit(1)
