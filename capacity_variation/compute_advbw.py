#!/usr/bin/python

import sys
import json
import lzma

from numpy import mean, median, std

def main():
    #with lzma.open('tor.archive.json.xz') as inf:
    with open('tor.archive.json', 'r') as inf:
        tor_archive = json.load(inf)

    relays = tor_archive['relays']
    #cons = tor_archive['cons_times']

    relay_adv_bw = {}
    for fp in relays:
        adv_bws = []

        for ts_str in relays[fp]["sdesc_timeline"]:
            adv_bws.append(int(relays[fp]["sdesc_timeline"][ts_str]['adv_bw']))

        if len(adv_bws) > 0:
            relay_adv_bw[fp] = mean(adv_bws)

    with lzma.open("relay_advbw.json.xz", 'wt') as outf:
        json.dump(relay_adv_bw, outf, indent=2)

if __name__ == '__main__': sys.exit(main())
