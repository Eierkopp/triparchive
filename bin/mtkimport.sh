#!/bin/bash

BASEDIR=`dirname $0`/..

. $BASEDIR/triparchive_env/bin/activate

export PYTHONPATH=$BASEDIR

python -m triptools.mtkimport --basedir $BASEDIR --config $BASEDIR/config/triparchive.conf $*

