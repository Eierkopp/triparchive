#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import io
import logging
import re
import sys
from urllib.request import urlopen
from zipfile import ZipFile

from triptools import config
from triptools import DB

logging.basicConfig(level=logging.INFO)

FEATURES = ["LONG", "LAT", "FULL_NAME_RO", "FC"]

def get_country_table():
    url = config.get("GNS", "names_url")
    response = urlopen(url)
    data = response.read()
    expr = re.compile(r'<a href="(cntyfile/[a-z]+.zip)" name="."> ([A-Z ,\(\)]+)</a>')
    data = data.decode("utf8")
    result = dict()
    for line in data.splitlines():
        m = expr.search(line)
        if m:
            result[m.group(2).lower()] = m.group(1)
    return result

def fetch_indexes(fields, spec):
    indexes = []
    spec = spec.split("\t")
    for field in fields:
        indexes.append(spec.index(field))
    return indexes
  
def unzip(data):
    data_file = io.BytesIO(data)
    zf = ZipFile(data_file)
    complete_name = zf.namelist()[0]
    if len(complete_name) != 6:
        raise Exception("Zip archive mismatch, please file an issue")
    complete_file = zf.open(complete_name)
    data = complete_file.read()
    return data

def import_line(conn, country_id, values):
    lon, lat, name, feature = values
    
def import_gns(country, url):
    url = config.get("GNS", "base_url") + url
    response = urlopen(url)
    data = response.read()
    data = unzip(data).decode("utf8")
    lines = data.splitlines()
    indexes = fetch_indexes(FEATURES, lines[0])

    with DB() as db:
        db.remove_gns(country)
        count = 0
        gns = db.geonetnames()
        for line in lines[1:]:
            line = line.split("\t")
            count += db.add_gns(gns, country, float(line[indexes[0]]), float(line[indexes[1]]), line[indexes[2]], line[indexes[3]])

    logging.getLogger(__name__).info("geonetnames for '%s' imported, %d entries added to DB" % (country, count))
    
if __name__ == "__main__":

    try:
        countries = get_country_table()
        country = config.get("GNS", "country").lower()
        if not country:
            print("country list:")
            for name in countries:
                print(name)
        else:
            if country in countries:
                import_gns(country, countries[country])
            else:
                raise Exception("unknown country: %s" % country)

    except Exception as e:
        logging.getLogger(__name__).error(e, exc_info=True)
        sys.exit(1)
