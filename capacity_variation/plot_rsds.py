#!/usr/bin/python

import sys
import os
import json
import lzma

from datetime import datetime

import matplotlib
matplotlib.use('Agg') # for systems without X11
import matplotlib.pyplot as pyplot
from matplotlib.backends.backend_pdf import PdfPages
from matplotlib.ticker import MultipleLocator

from numpy import arange, isnan, mean, median, std
from scipy.stats import scoreatpercentile as score
from scipy.stats import linregress

def main():
    with lzma.open('relay_rsds.json.xz') as inf:
        relay_rsds = json.load(inf)
    with lzma.open('relay_uptime.json.xz') as inf:
        relay_uptime = json.load(inf)
    with lzma.open('relay_position.json.xz') as inf:
        relay_position = json.load(inf)
    with lzma.open('relay_advbw.json.xz') as inf:
        relay_advbw = json.load(inf)
    with lzma.open('relay_weights.json.xz') as inf:
        relay_weights = json.load(inf)

    set_plot_options()

    plot_rsd_position(relay_rsds, relay_position)
    plot_rsd_uptime(relay_rsds, relay_uptime)
    plot_rsd_capacity(relay_rsds, relay_advbw)
    plot_rsd_weight(relay_rsds, relay_weights)

def plot_rsd_weight(relay_rsds, relay_weights):
    filename = "capacity_rsds_weight_cdf.pdf"
    print(filename)

    all_weight = sorted([relay_weights[fp] for fp in relay_rsds if fp in relay_weights])
    cut_low = all_weight[int(len(all_weight)/3.0)]
    cut_high = all_weight[int(2.0*len(all_weight)/3.0)]

    fig = pyplot.figure()

    all = [relay_rsds[fp]*100.0 for fp in relay_rsds]

    low = [relay_rsds[fp]*100.0 for fp in relay_rsds \
        if fp in relay_weights and relay_weights[fp] <= cut_low]
    mid = [relay_rsds[fp]*100.0 for fp in relay_rsds \
        if fp in relay_weights and relay_weights[fp] > cut_low and relay_weights[fp] <= cut_high]
    high = [relay_rsds[fp]*100.0 for fp in relay_rsds \
        if fp in relay_weights and relay_weights[fp] > cut_high]

    x, y = getcdf(all)
    label = "All"
    pyplot.plot(x, y, label=label, ls='-')
    print_stats(label, all)

    x, y = getcdf(low)
    label = r"Low 3rd: Sel. Prob. $\leq$ {{{w}}}\%".format(w=round(cut_low, 5))
    pyplot.plot(x, y, label=label, ls='--')
    print_stats(label, low)

    x, y = getcdf(mid)
    label = r"Mid 3rd: {{{w1}}} $<$ Sel. Prob. $\leq$ {{{w2}}}\%".format(w1=round(cut_low, 5), w2=round(cut_high, 3))
    pyplot.plot(x, y, label=label, ls='-.')
    print_stats(label, mid)

    x, y = getcdf(high)
    label = r"High 3rd: Sel. Prob. $>$ {{{w}}}\%".format(w=round(cut_high, 3))
    pyplot.plot(x, y, label=label, ls=':')
    print_stats(label, high)

    pyplot.ylabel('CDF over Relays')
    pyplot.xlabel('Mean Weekly Relative Standard Deviation (\%)')
    pyplot.xlim(xmin=-5, xmax=205.0)
    #pyplot.xscale('log')
    pyplot.legend()

    pyplot.tight_layout(pad=0.3)
    pyplot.savefig(filename)

def plot_rsd_capacity(relay_rsds, relay_advbw):
    filename = "capacity_rsds_advbw_cdf.pdf"
    print(filename)

    all_bw = sorted([relay_advbw[fp] for fp in relay_rsds if fp in relay_advbw])
    cut_low = all_bw[int(len(all_bw)/3.0)]
    cut_high = all_bw[int(2.0*len(all_bw)/3.0)]

    fig = pyplot.figure()

    all = [relay_rsds[fp]*100.0 for fp in relay_rsds]

    low = [relay_rsds[fp]*100.0 for fp in relay_rsds \
        if fp in relay_advbw and relay_advbw[fp] <= cut_low]
    mid = [relay_rsds[fp]*100.0 for fp in relay_rsds \
        if fp in relay_advbw and relay_advbw[fp] > cut_low and relay_advbw[fp] <= cut_high]
    high = [relay_rsds[fp]*100.0 for fp in relay_rsds \
        if fp in relay_advbw and relay_advbw[fp] > cut_high]

    x, y = getcdf(all)
    label = "All"
    pyplot.plot(x, y, label=label, ls='-')
    print_stats(label, all)

    x, y = getcdf(low)
    label = r"Low 3rd: BW $\leq$ {{{bw}}} Mbit/s".format(bw=round(cut_low/125000, 2))
    pyplot.plot(x, y, label=label, ls='--')
    print_stats(label, low)

    x, y = getcdf(mid)
    label = r"Mid 3rd: {{{bw1}}} $<$ BW $\leq$ {{{bw2}}} Mbit/s".format(bw1=round(cut_low/125000, 2), bw2=round(cut_high/125000, 1))
    pyplot.plot(x, y, label=label, ls='-.')
    print_stats(label, mid)

    x, y = getcdf(high)
    label = r"High 3rd: BW $>$ {{{bw}}} Mbit/s".format(bw=round(cut_high/125000, 1))
    pyplot.plot(x, y, label=label, ls=':')
    print_stats(label, high)

    pyplot.ylabel('CDF over Relays')
    pyplot.xlabel('Mean Weekly Relative Standard Deviation (\%)')
    pyplot.xlim(xmin=-5, xmax=205.0)
    #pyplot.xscale('log')
    pyplot.legend()

    pyplot.tight_layout(pad=0.3)
    pyplot.savefig(filename)

def plot_rsd_uptime(relay_rsds, relay_uptime):
    filename = "capacity_rsds_uptime_cdf.pdf"
    print(filename)

    cut_low = 100.0/3.0
    cut_high = 2.0*100.0/3.0

    fig = pyplot.figure()

    all = [relay_rsds[fp]*100.0 for fp in relay_rsds]
    low = [relay_rsds[fp]*100.0 for fp in relay_rsds \
        if fp in relay_uptime and relay_uptime[fp] <= cut_low]
    mid = [relay_rsds[fp]*100.0 for fp in relay_rsds \
        if fp in relay_uptime and relay_uptime[fp] > cut_low and relay_uptime[fp] <= cut_high]
    high = [relay_rsds[fp]*100.0 for fp in relay_rsds \
        if fp in relay_uptime and relay_uptime[fp] > cut_high]

    x, y = getcdf(all)
    label = "All"
    pyplot.plot(x, y, label=label, ls='-')
    print_stats(label, all)

    x, y = getcdf(low)
    label = "Low 3rd: Uptime $\leq$ 121 Days"
    pyplot.plot(x, y, label=label, ls='--')
    print_stats(label, low)

    x, y = getcdf(mid)
    label = "Mid 3rd: 121 $<$ Uptime $\leq$ 243 Days"
    pyplot.plot(x, y, label=label, ls='-.')
    print_stats(label, mid)

    x, y = getcdf(high)
    label = "High 3rd: Uptime $>$ 243 Days"
    pyplot.plot(x, y, label=label, ls=':')
    print_stats(label, high)

    pyplot.ylabel('CDF over Relays')
    pyplot.xlabel('Mean Weekly Relative Standard Deviation (\%)')
    pyplot.xlim(xmin=-5, xmax=205.0)
    #pyplot.xscale('log')
    pyplot.legend()

    pyplot.tight_layout(pad=0.3)
    pyplot.savefig(filename)

def plot_rsd_position(relay_rsds, relay_position):
    filename = "capacity_rsds_position_cdf.pdf"
    print(filename)

    fig = pyplot.figure()

    all = [relay_rsds[fp]*100.0 for fp in relay_rsds]
    exit = [relay_rsds[fp]*100.0 for fp in relay_rsds if get_relay_position(relay_position, fp) == 'exit']
    guard = [relay_rsds[fp]*100.0 for fp in relay_rsds if get_relay_position(relay_position, fp) == 'guard']
    middle = [relay_rsds[fp]*100.0 for fp in relay_rsds if get_relay_position(relay_position, fp) == 'middle']

    x, y = getcdf(all)
    label = "All"
    pyplot.plot(x, y, label=label, ls='-')
    print_stats(label, all)

    x, y = getcdf(exit)
    label = "Exit Position"
    pyplot.plot(x, y, label=label, ls='--')
    print_stats(label, exit)

    x, y = getcdf(guard)
    label = "Guard Position"
    pyplot.plot(x, y, label=label, ls='-.')
    print_stats(label, guard)

    x, y = getcdf(middle)
    label = "Middle Position"
    pyplot.plot(x, y, label=label, ls=':')
    print_stats(label, middle)

    pyplot.ylabel('CDF over Relays')
    pyplot.xlabel('Mean Weekly Relative Standard Deviation (\%)')
    pyplot.xlim(xmin=-5, xmax=205.0)
    #pyplot.xscale('log')
    pyplot.legend()

    pyplot.tight_layout(pad=0.3)
    pyplot.savefig(filename)

def get_relay_position(relays, fp):
    if fp not in relays:
        return 'na'
    p = relays[fp]
    if p['exit'] > p['guard'] and p['exit'] > p['middle']:
        return 'exit'
    elif p['guard'] > p['exit'] and p['guard'] > p['middle']:
        return 'guard'
    else:
        return 'middle'

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
        'legend.borderaxespad' : 0.5,
        'legend.numpoints' : 1,
        'legend.handletextpad' : 0.5,
        'legend.handlelength' : 2.0,
        'legend.labelspacing' : .75,
        'legend.markerscale' : 1.0,
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
    print("\tlength={}\n\tmin={}\n\t10={}\n\tq1={}\n\tmedian={}\n\tq3={}\n\t90={}\n\tmax={}\n\tmean={}\n\tstddev={}".format(len(b), min(b), score(b, 10), score(b, 25), median(b), score(b, 75), score(b, 90), max(b), mean(b), std(b)))

if __name__ == '__main__': main()
