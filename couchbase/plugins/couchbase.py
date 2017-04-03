#!/usr/bin/env python
import sys
import requests
import StringIO
from requests.auth import HTTPBasicAuth

from outlyer.plugin_helper.container import patch_all
patch_all()


# settings

USER = 'admin'
PASSWORD = 'password'
URL = 'http://localhost:8091'

# constants

success_message = "OK | "
failure_message = "CRITICAL | "
buf = StringIO.StringIO()
healthy = True
auth = HTTPBasicAuth(USER, PASSWORD)

# functions


def average_list(l):
    try:
        return reduce(lambda x, y: x + y, l) / float(len(l))
    except TypeError:
        pass


def flatten(structure, key="", path="", flattened=None):
    if flattened is None:
        flattened = {}
    if type(structure) not in (dict, list):
        flattened[((path + ".") if path else "") + key] = structure
    elif isinstance(structure, list):
        if len(structure) > 1:
            flattened[path + '.' + key] = average_list(structure)
        else:
            for i, item in enumerate(structure):
                flatten(item, "%d" % i, path + "." + key, flattened)
    else:
        for new_key, value in structure.items():
            flatten(value, new_key, path + "." + key, flattened)
    return flattened


def bytes_to_gb(num):
    return round(float(num) / 1024 / 1024 / 1024, 2)


# pools

try:
    default_pool = requests.get(URL + '/pools/default', auth=auth, timeout=5).json()
except Exception, e:
    print "Plugin Failed! Unable to connect to %s: %s" % (URL, e)
    sys.exit(2)

# health

for node in default_pool['nodes']:
    if node['status'] != 'healthy':
        healthy = False

# storage

storage_totals = default_pool['storageTotals']

for k, v in flatten(storage_totals, key='totals', path='storage').iteritems():
    if type(v) is int or type(v) is float:
        metric_path = k.lower()
        buf.write('{0}={1};;;; '.format(metric_path, v))
        buf.write('{0}_gb={1}GB;;;; '.format(metric_path, bytes_to_gb(v)))

nodes = default_pool['nodes']

# nodes

for node in nodes:
    if node['thisNode']:
        for k, v in flatten(node, key='stats', path='node').iteritems():
            if type(v) is int or type(v) is float:
                metric_path = k.lower()
                buf.write('{0}={1};;;; '.format(metric_path, v))

# buckets

try:
    buckets = requests.get(URL + '/pools/default/buckets', auth=auth, timeout=60).json()
except requests.HTTPError:
    buckets = []

bucket_names = []
for bucket in buckets:
    bucket_names.append(bucket['name'])

for name in bucket_names:
    bucket = requests.get(URL + '/pools/default/buckets/%s/stats?zoom=minute' % name, auth=auth, timeout=60).json()
    for k, v in flatten(bucket, key=name, path='bucket').iteritems():
        if type(v) is int or type(v) is float:
            metric_path = k.lower()
            buf.write('{0}={1};;;; '.format(metric_path, v))

if healthy:
    print success_message + buf.getvalue()
    sys.exit(0)
else:
    print failure_message + buf.getvalue()
    sys.exit(2)
