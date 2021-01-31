#!/usr/bin/python

import sys
import os
import json
import lzma

def main():
    #with lzma.open('tor.archive.json.xz') as inf:
    with open('tor.archive.json') as inf:
        tor_archive = json.load(inf)

    relay_freq = {}

    for fp in tor_archive['relays']:
        cons = tor_archive['relays'][fp]['cons_timeline']

        num_cons = len(cons)
        if num_cons == 0:
            continue

        # each consensus, you are either an exit, guard, or middle
        num_exit, num_guard, num_middle = 0, 0, 0

        for ts_str in cons:
            if cons[ts_str]["isexit"]:
                num_exit += 1
            elif cons[ts_str]["isguard"]:
                num_guard += 1
            else:
                num_middle += 1

        relay_freq[fp] = {
            'exit': 100.0*num_exit/num_cons,
            'guard': 100.0*num_guard/num_cons,
            'middle': 100.0*num_middle/num_cons,
        }

    with lzma.open('relay_position.json.xz', 'wt') as outf:
        json.dump(relay_freq, outf, indent=2)

if __name__ == '__main__':
    sys.exit(main())
