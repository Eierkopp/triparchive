#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import logging
import sys

from triptools import config
from triptools import DB

logging.basicConfig(level=logging.INFO)

    
if __name__ == "__main__":

    try:

        pass
        
    except Exception as e:
        logging.getLogger(__name__).error(e, exc_info=True)
        sys.exit(1)
