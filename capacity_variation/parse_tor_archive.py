#!/usr/bin/env python

import os
import sys
import json
import logging

from multiprocessing import Pool, cpu_count
from argparse import ArgumentParser, ArgumentDefaultsHelpFormatter
from datetime import datetime

from stem import Flag
from stem.descriptor import parse_file
from stem.descriptor import DocumentHandler
from stem.version import Version

# week 1 starts on 2018-08-01
MIN = datetime.strptime("2018-08-01 00:00:00", "%Y-%m-%d %H:%M:%S").timestamp()
# week 52 starts on 2019-07-24 and ends at the end of 2019-07-30
MAX = datetime.strptime("2019-07-31 00:00:00", "%Y-%m-%d %H:%M:%S").timestamp()

def main():
    args = get_args()
    setup_logging(args.logfile)

    cons_paths = get_file_list(args.consensuses)
    sdesc_paths = get_file_list(args.server_descriptors)

    worker_pool = Pool(cpu_count())

    logging.info("Processing {} consensus files...".format(len(cons_paths)))
    cons_results = parallelize(worker_pool, process_cons_file, cons_paths)
    logging.info("Got {} consensus results".format(len(cons_results)))

    logging.info("Processing {} server descriptor files...".format(len(sdesc_paths)))
    sdesc_results = parallelize(worker_pool, process_sdesc_file, sdesc_paths)
    logging.info("Got {} server descriptor results".format(len(sdesc_results)))

    logging.info("Merging all results...")
    relays, cons_times = merge_results(cons_results, sdesc_results)
    logging.info("Got {} relays".format(len(relays)))

    logging.info("Saving parsed data to disk as json")

    with open('tor.archive.json', 'w') as outf:
        json.dump({'relays': relays, 'cons_times': cons_times}, outf, indent=2)

    logging.info("All done!")

# this func is run by helper processes in process pool
def process_cons_file(path):
    net_status = next(parse_file(path, document_handler='DOCUMENT', validate=False))

    assert net_status.valid_after != None
    pub_ts = float(net_status.valid_after.strftime("%s"))
    if pub_ts < MIN or pub_ts >= MAX: return None

    cons_bw_sum = 0
    relays = {}

    for (fp, router_entry) in net_status.routers.items():
        if router_entry.bandwidth != None:
            bw = int(router_entry.bandwidth)
            is_unmeasured = router_entry.is_unmeasured
            relays.setdefault(fp, {'bw': bw, 'isunmeasured': is_unmeasured, \
                "isexit": True if "Exit" in router_entry.flags else False, \
                "isguard": True if "Guard" in router_entry.flags else False})
            cons_bw_sum += bw

    result = {
        'pub_ts': pub_ts,
        'relays': {},
    }

    for (fp, d) in relays.items():
        result['relays'][fp] = {
            "weight": float(d['bw'])/float(cons_bw_sum),
            "isunmeasured": d['isunmeasured'],
            "isexit": d['isexit'],
            "isguard": d['isguard'],
        }

    return result

# this func is run by helper processes in process pool
def process_sdesc_file(path):
    relay = next(parse_file(path, document_handler='DOCUMENT', descriptor_type='server-descriptor 1.0', validate=False))

    if relay.observed_bandwidth == None:
        return None

    assert relay.published != None
    pub_ts = float(relay.published.strftime("%s"))
    if pub_ts < MIN or pub_ts >= MAX: return None

    obs_bw = int(relay.observed_bandwidth)
    avg_bw, brst_bw = 0, 0

    advertised_bw = obs_bw

    if relay.average_bandwidth != None:
        avg_bw = int(relay.average_bandwidth)
        advertised_bw = min(advertised_bw, avg_bw)

    if relay.burst_bandwidth != None:
        brst_bw = int(relay.burst_bandwidth)
        advertised_bw = min(advertised_bw, brst_bw)

    #'nickname': relay.nickname,
    result = {
        'fprint': relay.fingerprint,
        'pub_ts': pub_ts,
        'adv_bw': advertised_bw,
        'obs_bw': obs_bw,
        'avg_bw': avg_bw,
        'brst_bw': brst_bw,
    }

    return result

def merge_results(cons_results, sdesc_results):
    relays = {}
    cons_times = []

    for result in cons_results:
        if result is None: continue

        ts = float(result['pub_ts'])
        cons_times.append(ts)

        for fp in result['relays']:
            relay = relays.setdefault(fp, {'cons_timeline': {}, 'sdesc_timeline': {}})
            relay['cons_timeline'][ts] = result['relays'][fp]

    for result in sdesc_results:
        if result is None: continue

        fp = result['fprint']
        ts = float(result['pub_ts'])
        adv_bw = int(result['adv_bw'])
        obs_bw = int(result['obs_bw'])
        avg_bw = int(result['avg_bw'])
        brst_bw = int(result['brst_bw'])

        # only inlude server descriptors within the consensus period
        if ts < min(cons_times) or ts > max(cons_times):
            continue

        relay = relays.setdefault(fp, {'cons_timeline': {}, 'sdesc_timeline': {}})
        relay['sdesc_timeline'][ts] = {'adv_bw':adv_bw, 'obs_bw':obs_bw, 'avg_bw':avg_bw, 'brst_bw':brst_bw}

    cons_times.sort()

    return relays, cons_times

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
        format='%(asctime)s %(created)f [collector-parser] [%(levelname)s] %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S',
        handlers=[file_handler, stdout_handler],
    )

    logging.info("Logging system initialized! Logging events to stdout and to '{}'".format(logfilename))

def get_file_list(dir_path):
    file_paths = []
    for root, _, filenames in os.walk(dir_path):
        for filename in filenames:
            file_paths.append(os.path.join(root, filename))
    return file_paths

def get_args():
    parser = ArgumentParser(
            description='Parse a set of archived collector consensus and server descriptors',
            formatter_class=CustomHelpFormatter)

    parser.add_argument('consensuses', help="Path to a directory containing multiple consensus files", metavar="PATH")
    parser.add_argument('server_descriptors', help="Path to a directory containing multiple server descriptor files", metavar="PATH")
    parser.add_argument('-l', '--logfile', help="Name of the file to store log output in addition to stdout", metavar="PATH", default="parser.log")

    args = parser.parse_args()
    return args

class CustomHelpFormatter(ArgumentDefaultsHelpFormatter):
    # adds the 'RawDescriptionHelpFormatter' to the ArgsDefault one
    def _fill_text(self, text, width, indent):
        return ''.join([indent + line for line in text.splitlines(True)])

if __name__ == "__main__":
    sys.exit(main())
