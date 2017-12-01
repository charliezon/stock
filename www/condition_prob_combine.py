#!/usr/bin/env python3
# -*- coding: utf-8 -*-

__author__ = 'Chaoliang Zhong'

import os
import json

new_cache = {}

def load_cache(path):
  cache = {}
  if not os.path.exists(path):
    return cache
  with open(path, 'r') as f:
    cache = json.load(f)
  return cache

def save_cache(path, cache):
  with open(path, 'w') as f:
  	f.write(json.dumps(cache))

old_cache = load_cache('data/old_cache.json')
complement_cache = load_cache('data/complement_cache.json')

for c in [old_cache, complement_cache]:
	for key in c:
	    keys = key.split(' and ')
	    if (len(keys) == 12 or len(keys) == 10):
	    	new_cache[key] = c[key]

save_cache('data/cache.json', new_cache)
