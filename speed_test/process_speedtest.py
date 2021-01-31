#!/usr/bin/env python

import os
import sys
import json
import lzma
import logging
import subprocess

from datetime import datetime
from multiprocessing import Pool, cpu_count
from argparse import ArgumentParser, ArgumentDefaultsHelpFormatter

from numpy import mean, median, std

MIN=datetime.strptime("2019-08-01 00:00:00", "%Y-%m-%d %H:%M:%S").timestamp()
START=datetime.strptime("2019-08-06 16:30:00", "%Y-%m-%d %H:%M:%S").timestamp()
# data from speedtest starts phasing out at: start + 18 hours + 5 days
STOP=datetime.strptime("2019-08-12 00:30:00", "%Y-%m-%d %H:%M:%S").timestamp()
MAX=datetime.strptime("2019-08-18 18:30:00", "%Y-%m-%d %H:%M:%S").timestamp()

def main():
    args = get_args()
    setup_logging(args.logfile)
    run(args)

def run(args):
    logging.info("Loading parsed json data from disk...")

    with lzma.open('speedtest.measured.json.xz') as inf:
        measured_fps = json.load(inf)
    with open('tor.archive.json', 'r') as inf: # from 2019-08-01 to 2019-08-21
        data = json.load(inf)

    logging.info("done.")

    worker_pool = Pool(cpu_count())

    logging.info("Processing data...")

    advbw_over_time = {ts: {'total':0, 'measured':0, 'unmeasured':0} for ts in data['cons_times']}
    speedtest = {}

    work = [[fp, data['relays'][fp], data['cons_times']] for fp in data['relays']]
    for result in parallelize(worker_pool, process_relay_data, work):
        if result == None:
            continue
        fp, relay_data, relay_advbw_over_time = result
        speedtest[fp] = relay_data

        for ts in relay_advbw_over_time:
            advbw_over_time[ts]['total'] += relay_advbw_over_time[ts]
            if fp in measured_fps:
                advbw_over_time[ts]['measured'] += relay_advbw_over_time[ts]
            else:
                advbw_over_time[ts]['unmeasured'] += relay_advbw_over_time[ts]

    logging.info("Got results for {} relays.".format(len(speedtest)))
    with lzma.open('speedtest.diffs.json.xz', 'wt') as outf:
        json.dump(speedtest, outf, indent=2)
    with lzma.open('advbw_over_time.json.xz', 'wt') as outf:
        json.dump(advbw_over_time, outf, indent=2)

    logging.info("All done!")

def process_relay_data(params):
    fp, relay_data, cons_times = params

    if 'cons_timeline' not in relay_data or 'sdesc_timeline' not in relay_data:
        return None

    ct = relay_data['cons_timeline']
    st = relay_data['sdesc_timeline']

    #####
    ##### first compute differences between before and after speedtest
    #####

    weights_before = [float(ct[k]) for k in ct if float(k) > MIN and float(k) <= START]
    weights_after = [float(ct[k]) for k in ct if float(k) > START and float(k) <= STOP]

    advbws_before = [int(st[k]) for k in st if float(k) > MIN and float(k) <= START]
    advbws_after = [int(st[k]) for k in st if float(k) > START and float(k) <= STOP]

    w_before = mean(weights_before) if len(weights_before) > 0 else 0
    w_after = mean(weights_after) if len(weights_after) > 0 else 0
    a_before = max(advbws_before) if len(advbws_before) > 0 else 0
    a_after = max(advbws_after) if len(advbws_after) > 0 else 0

    if w_before == 0 or w_after == 0 or a_before == 0 or a_after == 0:
        return None

    speedtest = {
        'weight': {
            'before': w_before,
            'after': w_after,
        },
        'advbw': {
            'before': a_before,
            'after': a_after,
        },
    }

    #####
    ##### now compute total adv bandwidth overall
    #####

    advbw_over_time = {ts: 0 for ts in cons_times}

    # only count adv bw when the relay is in the consensus
    for ts_str in ct:
        cons_ts = float(ts_str)
        advbw_over_time[cons_ts] += get_advbw(cons_ts, st)

    return [fp, speedtest, advbw_over_time]

def get_advbw(cons_ts, st):
    # find the first sdesc published before the consensus
    sdesc_times = sorted([float(ts_str) for ts_str in st], reverse=True)
    for sdesc_ts in sdesc_times:
        if sdesc_ts <= cons_ts:
            return int(st[str(sdesc_ts)])
    return 0

def parallelize(worker_pool, func, work, batch_size=10000):
    all_results = []
    work_batches = [work[i:i+batch_size] for i in range(0, len(work), batch_size)]

    logging.info("Parallelizing {} work tasks in {} batch(es)".format(len(work), len(work_batches)))

    for i, work_batch in enumerate(work_batches):
        try:
            logging.info("Running batch {}/{}".format(i+1, len(work_batches)))
            results = worker_pool.map(func, work_batch)
            all_results.extend(results)
        except KeyboardInterrupt:
            print >> sys.stderr, "interrupted, terminating process pool"
            worker_pool.terminate()
            worker_pool.join()
            sys.exit(1)

    return all_results

def setup_logging(logfilename):
    file_handler = logging.FileHandler(filename=logfilename)
    stdout_handler = logging.StreamHandler(sys.stdout)

    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s %(created)f [processor] [%(levelname)s] %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S',
        handlers=[file_handler, stdout_handler],
    )

    logging.info("Logging system initialized! Logging events to stdout and to '{}'".format(logfilename))

def get_args():
    parser = ArgumentParser(
            description='Process capacity data produced with parse_tor_archive.py',
            formatter_class=CustomHelpFormatter)

    parser.add_argument('-l', '--logfile', help="Name of the file to store log output in addition to stdout", metavar="PATH", default="processor.log")

    args = parser.parse_args()
    return args

class CustomHelpFormatter(ArgumentDefaultsHelpFormatter):
    # adds the 'RawDescriptionHelpFormatter' to the ArgsDefault one
    def _fill_text(self, text, width, indent):
        return ''.join([indent + line for line in text.splitlines(True)])

if __name__ == "__main__":
    sys.exit(main())
