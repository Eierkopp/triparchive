from configparser import SafeConfigParser, ExtendedInterpolation
from functools import lru_cache
import argparse
import logging
import os
import sys
import warnings
import traceback
import types

MOVIE_PROFILE_PREFIX = "Movie_Profile_"

# disable warnings
warnings.filterwarnings("ignore", message=".*")

logging.basicConfig(level=logging.INFO)

class WideHelpFormatter(argparse.ArgumentDefaultsHelpFormatter):
    def __init__(self, *args, **kwargs):
        kwargs["max_help_position"] = 8
        kwargs["width"] = 80
        super(WideHelpFormatter, self).__init__(*args, **kwargs)

def argname(section, option):
    return (section + "_" + option).lower()

parser = argparse.ArgumentParser(prog='triparchive',
                                 formatter_class=WideHelpFormatter)

parser.add_argument("--basedir",
                    help="installation directory",
                    dest="basedir",
                    required=True)

parser.add_argument("--config",
                    help="configuration file location",
                    dest="config",
                    required=True)

parser.add_argument("--exthelp",
                    help="extended help",
                    dest="exthelp",
                    action="store_true")

args = parser.parse_known_args()[0]
args.basedir = os.path.abspath(args.basedir)

conf_file = os.getenv('TRIPARCHIVE_CONF', args.config)

class log_after:

    def __init__(self):
        self.known = set()
    
    def __call__(self, result, section, param, *args, **kwargs):
        if (section, param) in self.known:
            return
        self.known.add((section, param))
        print("%s_%s=%s" % (section.lower(), param.lower(), result))
        

def wrap_method(instance, orig_method, before_call=None, after_call=None):

    def wrapped(self, *args, **kwargs):
        if before_call: before_call(*args, **kwargs)
        result = orig_method(*args, **kwargs)
        if after_call: after_call(result, *args, **kwargs)
        return result
    
    return types.MethodType(wrapped, instance)



config = SafeConfigParser(interpolation=ExtendedInterpolation(),
                          defaults={"basedir" : args.basedir})

config.read(conf_file)

parser = argparse.ArgumentParser(prog='triparchive',
                                 formatter_class=WideHelpFormatter)

parser.add_argument("--basedir",
                    help="installation directory",
                    dest="basedir",
                    required=True)

parser.add_argument("--config",
                    help="configuration file location",
                    dest="config",
                    required=True)

parser.add_argument("--exthelp",
                    help="extended help",
                    dest="exthelp",
                    action="store_true")

for section in config.sections():
    for option in config.options(section):
        if not option.endswith("_help") and config.has_option(section, option + "_help"):
            parser.add_argument("--%s" % argname(section, option),
                                help=config.get(section, option + "_help"),
                                dest=argname(section, option),
                                default=config.get(section, option))

if args.exthelp:
    parser.print_help()
    sys.exit(0)

args = parser.parse_args()

for section in config.sections():
    for option in config.options(section):
        if (not option.endswith("_help")
            and config.has_option(section, option + "_help")
            and hasattr(args, argname(section, option))):
            config.set(section, option, getattr(args, argname(section, option)))

config.get = wrap_method(config, config.get, after_call=log_after())
