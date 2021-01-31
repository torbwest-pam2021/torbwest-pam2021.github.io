#!/usr/bin/python

import sys
import json
import lzma

from numpy import mean

def main():
    #with lzma.open('tor.archive.json.xz') as inf:
    with open('tor.archive.json', 'r') as inf:
        tor_archive = json.load(inf)

    relays = tor_archive['relays']

    relay_weights = {}

    for fp in relays:
        weights_normed = list(d['weight'] for d in relays[fp]["cons_timeline"].values())
        if len(weights_normed) > 0:
            relay_weights[fp] = 100.0*mean(weights_normed)

    with lzma.open('relay_weights.json.xz', 'wt') as outf:
        json.dump(relay_weights, outf, indent=2)

if __name__ == '__main__': sys.exit(main())
