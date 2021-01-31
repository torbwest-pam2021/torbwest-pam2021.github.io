#!/usr/bin/python

import sys
import os
import lzma
import json

from datetime import datetime

import matplotlib
matplotlib.use('Agg') # for systems without X11
import matplotlib.pyplot as pyplot
from matplotlib.backends.backend_pdf import PdfPages

from numpy import arange, isnan, mean, median, std
from scipy.stats import scoreatpercentile as score
from scipy.stats import linregress

MIN = datetime.strptime("2019-08-01 00:00:00", "%Y-%m-%d %H:%M:%S").timestamp()
SPEEDTEST_START_TS = datetime.strptime("2019-08-06 16:30:00", "%Y-%m-%d %H:%M:%S").timestamp()
SPEEDTEST_END_TS = datetime.strptime("2019-08-08 19:45:00", "%Y-%m-%d %H:%M:%S").timestamp()
BW_EXPIRE_START_TS = SPEEDTEST_START_TS + 5*24*3600.0 # bw hists start expiring 5 days after speed test
BW_EXPIRE_END_TS = BW_EXPIRE_START_TS + (SPEEDTEST_END_TS-SPEEDTEST_START_TS)
MAX=datetime.strptime("2019-08-18 18:30:00", "%Y-%m-%d %H:%M:%S").timestamp()

def main():
    set_plot_options()

    with lzma.open('advbw_over_time.json.xz') as inf:
        advbw_over_time = json.load(inf)

    times = sorted([float(ts_str) for ts_str in advbw_over_time])

    periods = {}
    x, y_total, y_measured, y_unmeasured = [], [], [], []
    for i, ts in enumerate(times):
        if i < 24: continue # skip the first
        if ts > MAX: continue # no need to extend too far

        total = advbw_over_time[str(ts)]['total']/125000000.0 # bytes to gbit/s
        measured = advbw_over_time[str(ts)]['measured']/125000000.0 # bytes to gbit/s
        unmeasured = advbw_over_time[str(ts)]['unmeasured']/125000000.0 # bytes to gbit/s

        x.append(datetime.fromtimestamp(ts))

        y_total.append(total)
        y_measured.append(measured)
        y_unmeasured.append(unmeasured)

        if ts > MIN and ts <= SPEEDTEST_START_TS: # before speed test
            periods.setdefault('before', {}).setdefault('total', []).append(total)
            periods.setdefault('before', {}).setdefault('measured', []).append(measured)
            periods.setdefault('before', {}).setdefault('unmeasured', []).append(unmeasured)
        elif ts > SPEEDTEST_END_TS and ts <= BW_EXPIRE_START_TS: # after speed test, during updated bw histories
            periods.setdefault('during', {}).setdefault('total', []).append(total)
            periods.setdefault('during', {}).setdefault('measured', []).append(measured)
            periods.setdefault('during', {}).setdefault('unmeasured', []).append(unmeasured)
        elif ts > BW_EXPIRE_END_TS and ts <= MAX: # after bw histories expire
            periods.setdefault('after', {}).setdefault('total', []).append(total)
            periods.setdefault('after', {}).setdefault('measured', []).append(measured)
            periods.setdefault('after', {}).setdefault('unmeasured', []).append(unmeasured)

    f = pyplot.figure()

    l1 = pyplot.plot(x, y_total, c='C0', ls='-', label="Total")
    l2 = pyplot.plot(x, y_measured, c='C1', ls='--', label="Measured")
    l3 = pyplot.plot(x, y_unmeasured, c='C2', ls=':', label="Unmeasured")

    start = datetime.fromtimestamp(SPEEDTEST_START_TS)
    end = datetime.fromtimestamp(SPEEDTEST_END_TS)
    l4 = pyplot.fill_betweenx([0, 600], [start, start], [end, end], color='C8', alpha=0.4, zorder=0.5, label="Speed Test Active")

    start = datetime.fromtimestamp(BW_EXPIRE_START_TS)
    end = datetime.fromtimestamp(BW_EXPIRE_END_TS)
    l5 = pyplot.fill_betweenx([0, 600], [start, start], [end, end], color='C7', alpha=0.4, zorder=0.5, label="Speed Test BW\nHistories Expire")

    f.autofmt_xdate()
    pyplot.ylabel("Advertised Bandwidth (Gbit/s)")
    pyplot.ylim(ymin=0, ymax=600)

    # ax = pyplot.gca()
    # lines = ax.get_lines()
    # leg1 = pyplot.legend([lines[i] for i in [0,1,2]], [lines[i].get_label() for i in [0,1,2]], ncol=3, loc='center right')
    # leg2 = pyplot.legend([l4, l5], ['Speed Test Active', 'Speed Test BW\nHistories Expire'], loc="upper right")
    # pyplot.gca().add_artist(leg1)

    pyplot.legend(ncol=2, loc='upper right', bbox_to_anchor=(0.99, 0.5))

    pyplot.tight_layout(pad=0.3)
    pyplot.savefig("speedtest-timeseries.pdf")

    print("Stats from:\n\tbefore: before speed test started\n\tduring: after speed test ended but before histories started expiring\n\tafter: after histories expired")
    for p in sorted(periods.keys()):
        print("")
        for k in sorted(periods[p].keys()):
            print_stats(f"Period={p} sum={k}: ", periods[p][k])

def set_plot_options():
    options = {
        #'backend': 'PDF',
        'font.size': 12,
        'figure.figsize': (3,2.0),
        'figure.dpi': 100.0,
        'figure.subplot.left': 0.20,
        'figure.subplot.right': 0.97,
        'figure.subplot.bottom': 0.20,
        'figure.subplot.top': 0.90,
        'grid.color': '0.1',
        'grid.linestyle': ':',
        #'grid.linewidth': 0.5,
        'axes.grid' : True,
        #'axes.grid.axis' : 'y',
        #'axes.axisbelow': True,
        'axes.titlesize' : 'x-small',
        'axes.labelsize' : 8,
        'axes.formatter.limits': (-4,4),
        'xtick.labelsize' : 7,
        'ytick.labelsize' : 7,
        'lines.linewidth' : 2.0,
        'lines.markeredgewidth' : 0.5,
        'lines.markersize' : 2,
        'legend.fontsize' : 7,
        'legend.fancybox' : False,
        'legend.shadow' : False,
        'legend.borderaxespad' : 0.25,
        'legend.numpoints' : 1,
        'legend.handletextpad' : 0.5,
        'legend.handlelength' : 1.25,
        'legend.labelspacing' : .75,
        'legend.markerscale' : 1.0,
        'legend.columnspacing': 1.0,
        # turn on the following to embedd fonts; requires latex
        'ps.useafm' : True,
        'pdf.use14corefonts' : True,
        'text.usetex' : True,
    }

    for option_key in options:
        matplotlib.rcParams[option_key] = options[option_key]

    if 'figure.max_num_figures' in matplotlib.rcParams:
        matplotlib.rcParams['figure.max_num_figures'] = 50
    if 'figure.max_open_warning' in matplotlib.rcParams:
        matplotlib.rcParams['figure.max_open_warning'] = 50
    if 'legend.ncol' in matplotlib.rcParams:
        matplotlib.rcParams['legend.ncol'] = 50

## helper - cumulative fraction for y axis
def cf(d): return arange(1.0,float(len(d))+1.0)/float(len(d))

## helper - return step-based CDF x and y values
## only show to the 99th percentile by default
def getcdf(data, shownpercentile=1.0, maxpoints=100000.0):
    data.sort()
    frac = cf(data)
    k = len(data)/maxpoints
    x, y, lasty = [], [], 0.0
    for i in range(int(round(len(data)*shownpercentile))):
        if i % k > 1.0: continue
        assert not isnan(data[i])
        x.append(data[i])
        y.append(lasty)
        x.append(data[i])
        y.append(frac[i])
        lasty = frac[i]
    return x, y

def print_stats(msg, dist):
    b = sorted(dist)#.values()
    print(msg)
    print("min={} q1={} median={} q3={} max={} mean={} stddev={}".format(min(b), score(b, 25), median(b), score(b, 75), max(b), mean(b), std(b)))

if __name__ == '__main__': main()
