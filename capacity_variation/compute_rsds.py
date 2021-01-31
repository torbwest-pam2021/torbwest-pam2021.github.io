#!/usr/bin/env python

import os
import sys
import json
import lzma
import logging
import subprocess

from datetime import datetime
from multiprocessing import Pool, cpu_count

from numpy import mean, median, std

START = datetime.strptime("2018-08-01 00:00:00", "%Y-%m-%d %H:%M:%S").timestamp()
# week 52 starts on 2019-07-24 and ends at the end of 2019-07-30
END = datetime.strptime("2019-07-31 00:00:00", "%Y-%m-%d %H:%M:%S").timestamp()

def main():
    setup_logging()
    logging.info("Loading parsed json data from disk")

    data = load('tor.archive.json')

    # relays is of the form:
    # relays[fp]['cons_timeline'][ts] = cons_weight # normalized
    # relays[fp]['sdesc_timeline'][ts] = adv_bw # in bytes, not normalized
    relays = data['relays']
    cons_times = data['cons_times']
    logging.info("Got {} relays across {} consensus files".format(len(relays), len(cons_times)))

    worker_pool = Pool(cpu_count())
    relay_work = [[fp, relays[fp]] for fp in relays]
    results = parallelize(worker_pool, process_relay_data, relay_work, batch_size=100000)

    relay_rsds = merge(results)
    logging.info("Storing weekly mean rsd for {} relays".format(len(relay_rsds)))
    save(relay_rsds, 'relay_rsds.json.xz')

    logging.info("All done!")

def merge(results):
    # merge the results for all relays
    logging.info("Merging relay results...")
    relay_rsds = {}
    for item in results:
        if item == None:
            continue
        fp, mean_rsd = item
        relay_rsds[fp] = mean_rsd
    logging.info("Computed mean RSDs for {} relays".format(len(relay_rsds)))
    return relay_rsds

# this func is run by helper processes in process pool
def process_relay_data(params):
    fp = params[0]
    relay = params[1]

    '''
    for relays that were measured for at least a consensus, we compute the mean over the
    per week rel. std. dev. of their advertised bws over only those weeks where their
    bwrate or bwburst limits did not reduce the advertised bw
    '''

    ct = relay['cons_timeline']
    st = relay['sdesc_timeline']

    # ignore days where the relay was in an unmeasured status
    measured_days, unmeasured_days = {}, {}
    for ts_str in ct:
        ts = float(ts_str)
        if ts < START or ts >= END:
            continue

        day_num = int((ts - START)/3600.0/24.0)
        if ct[ts_str]['isunmeasured']:
            unmeasured_days.setdefault(day_num, []).append(ts)
        else:
            measured_days.setdefault(day_num, []).append(ts)

    # ignore relays that have not been in a measured state in at least one consensus
    if len(measured_days) == 0:
        return None

    # ignore weeks where the bw rate or burst reduced the advertised bw
    # each week is independent of other weeks
    adv_bw_limited_weeks = set()
    bw_lim_week = {}
    for ts_str in sorted(list(st.keys()), key=lambda x: float(x)):
        ts = float(ts_str)
        if ts < START or ts >= END:
            continue

        day_num = int((ts - START)/3600.0/24.0)
        week_num = int(day_num/7.0)
        bw_lim_week.setdefault(week_num, None)

        bwlim = min(int(st[ts_str]['avg_bw']), int(st[ts_str]['brst_bw']))

        if bw_lim_week[week_num] == None:
            bw_lim_week[week_num] = bwlim
        elif bwlim != bw_lim_week[week_num]:
            # OK the bwlim changed, but this will only affect our rsd variation
            # calculation if the bwlim was low enough to cause us to report a
            # different advertised bw than we normally would. This is only the
            # case if the observed and advertised bw are not the same.
            if int(st[ts_str]['adv_bw']) != int(st[ts_str]['obs_bw']):
                # the bw limits affected our adv bw this week
                adv_bw_limited_weeks.add(week_num)

    # bin the adv bw values into weeks accounting for the above constraints
    adv_bw_week = {}
    for ts_str in st:
        ts = float(ts_str)
        if ts < START or ts >= END:
            continue

        day_num = int((ts - START)/3600.0/24.0)
        week_num = int(day_num/7.0)

        #if day_num in unmeasured_days or week_num in adv_bw_limited_weeks:
        if week_num in adv_bw_limited_weeks:
            # a change in their rate limit reduced the adv bw this week, so
            # don't count it as variation
            continue
        elif day_num in measured_days and min(measured_days[day_num]) > ts:
            # we were not marked as measured until AFTER this descriptor, so skip it
            # we do this by day in case some relays go in and out of measured state over time
            continue

        adv_bw_week.setdefault(week_num, []).append(int(st[ts_str]['adv_bw']))

    # compute the rel. std. dev. for each week
    rsds = []
    for week_num in adv_bw_week:
        adv_bw = adv_bw_week[week_num]

        s, m = std(adv_bw), mean(adv_bw)
        if m > 0:
            rsds.append(s/m)

    if len(rsds) > 0:
        return [fp, mean(rsds)]
    else:
        return None

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

    logging.info("Got {} results".format(len(all_results)))
    return all_results

def load(data_path):
    filename = os.path.abspath(os.path.expanduser(data_path))
    if filename.endswith(".xz"):
        with lzma.open('tor.archive.json.xz') as fin:
            return json.load(fin)
    else:
        with open(filename, 'r') as fin:
            return json.load(fin)

def save(data, filename):
    logging.info("Saving parsed data to disk as json")
    with lzma.open(filename, 'wt') as outf:
        json.dump(data, outf, indent=2)
    logging.info("Done!")

def setup_logging():
    #file_handler = logging.FileHandler(filename=logfilename)
    stdout_handler = logging.StreamHandler(sys.stdout)

    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s %(created)f [processor] [%(levelname)s] %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S',
        #handlers=[file_handler, stdout_handler],
        handlers=[stdout_handler],
    )

    logging.info("Logging system initialized! Logging events to stdout.")

if __name__ == "__main__":
    sys.exit(main())
