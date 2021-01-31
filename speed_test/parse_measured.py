#!/usr/bin/env python36

import sys
import lzma
import json

def main():
    with lzma.open("speedtester.json.xz", 'r') as inf:
        data = json.load(inf)

    total = len(data['relays'])
    print(f"Got {total} relays")

    measured = set()
    unmeasured = set()
    for fp in data['relays']:
        if data['relays'][fp]['n_measured'] > 0:
            measured.add(fp)
        else:
            unmeasured.add(fp)

    print(f"Measured {len(measured)}/{total} relays, {len(unmeasured)}/{total} unmeasured")

    with lzma.open("speedtest.measured.json.xz", 'wt') as outf:
        json.dump(list(measured), outf, indent=2)

if __name__ == '__main__': sys.exit(main())
