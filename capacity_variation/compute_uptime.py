#!/usr/bin/python

import sys
import json
import lzma

he1_ips = ['65.19.167.130', '65.19.167.131', '65.19.167.132', '65.19.167.133', '65.19.167.134']
he2_ips = ['216.218.222.10', '216.218.222.11', '216.218.222.12', '216.218.222.13', '216.218.222.14']

def main():
    #with lzma.open('tor.archive.json.xz') as inf:
    with open('tor.archive.json', 'r') as inf:
        tor_archive = json.load(inf)
    #
    # with lzma.open('speedtest.diffs.json.xz') as inf:
    #     relay_diffs = json.load(inf)

    relays = tor_archive['relays']
    cons = tor_archive['cons_times']

    uptime = {fp: 100.0*len(relays[fp]["cons_timeline"])/len(cons) for fp in relays}

    with lzma.open('relay_uptime.json.xz', 'wt') as outf:
        json.dump(uptime, outf, indent=2)

if __name__ == '__main__': sys.exit(main())
