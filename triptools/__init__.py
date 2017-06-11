from .configuration import config
from .common import Trackpoint, Feature, distance
from .db_impl import DB
from .map_support import MapTool

osm_mapper = MapTool(config.get("Map", "redis_host"))
