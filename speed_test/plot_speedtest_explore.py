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

he1_ips = ['65.19.167.130', '65.19.167.131', '65.19.167.132', '65.19.167.133', '65.19.167.134']
he2_ips = ['216.218.222.10', '216.218.222.11', '216.218.222.12', '216.218.222.13', '216.218.222.14']

# not all plots are included in the paper
# normally this script only produces the plots for the paper
# if you set this to true, it will also produce plots that we did not include
GENERATE_EXTRA_PLOTS=False

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

def print_overall_stats(data, pos=None):
    if pos is not None:
        before = [float(item[0]) for item in data if item[5] == pos]
        after = [float(item[1]) for item in data if item[5] == pos]
        discovered = [float(item[1])-item[0] for item in data if item[5] == pos]
        weight_change = [abs(item[3]-item[2]) for item in data if item[5] == pos]
    else:
        before = [float(item[0]) for item in data]
        after = [float(item[1]) for item in data]
        discovered = [float(item[1])-item[0] for item in data]
        weight_change = [abs(item[3]-item[2]) for item in data]
    print(f"{'Total' if pos is None else pos} Tor Capacity absolute before experiment: {sum(before)} Mbit/s")
    print(f"{'Total' if pos is None else pos} Tor Capacity absolute after experiment: {sum(after)} Mbit/s")
    print(f"{'Total' if pos is None else pos} Tor Capacity absolute discovered by experiment: {sum(discovered)} Mbit/s")
    print(f"{'Total' if pos is None else pos} Tor Capacity relative increase: {100.0*sum(discovered)/sum(before)} \%")
    print(f"{'Total' if pos is None else pos} Tor Capacity relative discovered: {100.0*sum(discovered)/sum(after)} \%")
    print(f"{'Total' if pos is None else pos} absolute change is selection prob.: {100.0*sum(weight_change)} \%")

def load_filtered(measured_fps, filename):
    with lzma.open(filename) as inf:
        data = json.load(inf)
    if measured_fps is None:
        return data
    else:
        return {fp: data[fp] for fp in data if fp in measured_fps}

def load():
    # if you don't want to filter the relays down to only those that we were
    # able to actively measure, set measured_fps to None rather than loading
    # file here
    with lzma.open('speedtest.measured.json.xz') as inf:
        measured_fps = json.load(inf)

    relay_diffs = load_filtered(measured_fps, 'speedtest.diffs.json.xz')
    relay_uptime = load_filtered(measured_fps, 'relay_uptime.json.xz')
    relay_position = load_filtered(measured_fps, 'relay_position.json.xz')

    return relay_diffs, relay_uptime, relay_position

def main():
    relay_diffs, relay_uptime, relay_position = load()
    set_plot_options()

    data = []
    for fp in relay_diffs:
        if "advbw" in relay_diffs[fp] and "weight" in relay_diffs[fp] and \
                "before" in relay_diffs[fp]["advbw"] and \
                "after" in relay_diffs[fp]["advbw"] and \
                "before" in relay_diffs[fp]["weight"] and \
                "after" in relay_diffs[fp]["weight"]:
            cap_before = int(relay_diffs[fp]["advbw"]["before"])/125000.0 # bytes to mbits
            cap_after = int(relay_diffs[fp]["advbw"]["after"])/125000.0 # bytes to mbits

            weight_before = float(relay_diffs[fp]["weight"]["before"])
            weight_after = float(relay_diffs[fp]["weight"]["after"])

            percent_uptime = relay_uptime[fp] if fp in relay_uptime else 0
            position = get_relay_position(relay_position, fp)

            data.append([cap_before, cap_after, weight_before, weight_after, percent_uptime, position])

    # rank relays by "after" capacity
    data.sort(key=lambda item: item[1])

    # print some useful overall numbers
    print_overall_stats(data)
    print_overall_stats(data, 'exit')
    print_overall_stats(data, 'guard')
    print_overall_stats(data, 'middle')


    ########################
    filename = "speedtest_change_mbit_scatter.pdf"
    print(f"\n\n########################\n{filename}\n########################")

    fig = pyplot.figure()
    x = [item[0] for item in data] # before
    y = [item[1] for item in data] # after
    pyplot.scatter(x, y, s=0.3)

    mx = max(max(x), max(y))
    mn = min(min(x), min(y))
    pyplot.plot([mn, mx], [mn, mx], color="red", linestyle="dashed")

    pyplot.xscale('log')
    pyplot.yscale('log')
    pyplot.xlim(xmin=mn)
    pyplot.ylim(ymin=mn)
    pyplot.xticks([1.0, 10.0, 100.0, 1000.0])
    pyplot.yticks([1.0, 10.0, 100.0, 1000.0])

    pyplot.ylabel('Absolute Capacity After (Mbit/s)')
    pyplot.xlabel('Absolute Capacity Before (Mbit/s)')

    pyplot.tight_layout(pad=0.3)
    pyplot.savefig(filename)

    ########################
    if GENERATE_EXTRA_PLOTS:
        fig = pyplot.figure()
        x = [item[1] for item in data] # after
        y = [(item[1]-item[0])/item[1]*100.0 for item in data] # percent of after capacity that we discovered
        pyplot.scatter(x, y, s=0.3)

        pyplot.ylim(ymin=-100)

        pyplot.ylabel('Capacity Discovered (\%)')
        pyplot.xlabel('Capacity After (Mbit/s)')

        pyplot.tight_layout(pad=0.3)
        pyplot.savefig("speedtest_perc_discovered_scatter.pdf")

    ########################
    filename = "speedtest_perc_discovered_cdf.pdf"
    print(f"\n\n########################\n{filename}\n########################")

    fig = pyplot.figure()

    discovered_sorted_by_after = [(item[1]-item[0])/item[1]*100.0 for item in data] # percent discovered after
    after_data_range = [item[1] for item in data]
    plot_cdf_split(discovered_sorted_by_after, after_data_range, "Abs. Cap. After Rank")

    pyplot.ylabel('CDF')
    pyplot.xlabel('Relative Capacity Discovered (\%)')
    pyplot.xlim(xmin=-25)
    #pyplot.xscale('log')
    pyplot.legend()

    pyplot.tight_layout(pad=0.3)
    pyplot.savefig(filename)

    ########################
    if GENERATE_EXTRA_PLOTS:
        fig = pyplot.figure()
        x = [item[1] for item in data] # after
        y = [(item[1]-item[0])/item[0]*100.0 for item in data] # percent increased from before to after
        pyplot.scatter(x, y, s=0.3)

        pyplot.ylim(ymin=-100)

        pyplot.ylabel('Capacity Increased (\%)')
        pyplot.xlabel('Capacity After (Mbit/s)')

        pyplot.tight_layout(pad=0.3)
        pyplot.savefig("speedtest_perc_increased_scatter.pdf")

    ########################
    if GENERATE_EXTRA_PLOTS:
        fig = pyplot.figure()

        increase = [(item[1]-item[0])/item[0]*100.0 for item in data] # percent increase from before to after

        plot_cdf_split(increase, "After Rank")

        pyplot.ylabel('CDF')
        pyplot.xlabel('Capacity Increased (\%)')
        pyplot.xscale('log')

        pyplot.legend(loc="lower right")

        pyplot.tight_layout(pad=0.3)
        pyplot.savefig("speedtest_perc_increased_cdf.pdf")

    ########################
    filename = "speedtest_rank_discovered_plot.pdf"
    print(f"\n\n########################\n{filename}\n########################")

    fig = pyplot.figure()

    x = list(range(len(data)))
    y = [item[1]-item[0] for item in data]
    pyplot.scatter(x, y, s=0.3, label="Discovered")
    y = [item[1] for item in data]
    pyplot.plot(x, y, c='C1', label="Total")

    pyplot.ylabel('Absolute Capacity (Mbit/s)')
    pyplot.xlabel('Rank (Absolute Capacity After)')

    pyplot.legend()

    pyplot.tight_layout(pad=0.3)
    pyplot.savefig(filename)

    ########################
    if GENERATE_EXTRA_PLOTS:
        filename = "speedtest_rank_reldiscovered_plot.pdf"
        print(f"\n\n########################\n{filename}\n########################")

        fig = pyplot.figure()

        x = list(range(len(data)))
        y = [(item[1]-item[0])/item[1]*100.0 for item in data]
        pyplot.scatter(x, y, s=0.3, label="Discovered")
        #y = [item[1] for item in data]
        #pyplot.plot(x, y, c='C1', label="Total")

        pyplot.ylabel('Relative Capacity (\%)')
        pyplot.xlabel('Rank (Absolute Capacity After)')
        pyplot.ylim(ymin=-200, ymax=200)

        pyplot.legend()

        pyplot.tight_layout(pad=0.3)
        pyplot.savefig(filename)

    ########################
    filename = "speedtest_rank_discovered_ylog.pdf"
    print(f"\n\n########################\n{filename}\n########################")

    fig = pyplot.figure()

    x = list(range(len(data)))
    y = [item[1]-item[0] for item in data]
    pyplot.scatter(x, y, s=0.3, label="Discovered")
    y = [item[1] for item in data]
    pyplot.plot(x, y, c='C1', label="Total")

    pyplot.yscale('log')

    pyplot.ylabel('Absolute Capacity (Mbit/s)')
    pyplot.xlabel('Rank (Absolute Capacity After Speed Test)')

    pyplot.legend()

    pyplot.tight_layout(pad=0.3)
    pyplot.savefig(filename)

    ########################
    filename = "speedtest_rank_discovered_cdf.pdf"
    print(f"\n\n########################\n{filename}\n########################")

    fig = pyplot.figure()

    discovered_sorted_by_after = [item[1]-item[0] for item in data]
    after_data_range = [item[1] for item in data]
    plot_cdf_split(discovered_sorted_by_after, after_data_range, "Abs. Cap. After Rank")

    pyplot.ylabel('CDF')
    pyplot.xlabel('Absolute Capacity Discovered (Mbit/s)')

    pyplot.legend()

    pyplot.tight_layout(pad=0.3)
    pyplot.savefig(filename)

    ########################
    if GENERATE_EXTRA_PLOTS:
        fig = pyplot.figure()

        discovered = [item[1]-item[0] for item in data]

        plot_cdf_split(discovered, "After Rank")

        pyplot.ylabel('CDF')
        pyplot.xlabel('Capacity Discovered (Mbit/s)')
        pyplot.xscale('log')
        pyplot.xlim(xmin=1.0)

        pyplot.legend()

        pyplot.tight_layout(pad=0.3)
        pyplot.savefig("speedtest_rank_discovered_cdf_xlog.pdf")

    ########################
    if GENERATE_EXTRA_PLOTS:
        fig = pyplot.figure()
        uptime = [item[4] for item in data] # after
        discovered = [item[1]-item[0] for item in data]
        pyplot.scatter(discovered, uptime, s=0.3)

        pyplot.xlabel('Capacity Discovered (Mbit/s)')
        pyplot.ylabel('Uptime (\%)')

        pyplot.tight_layout(pad=0.3)
        pyplot.savefig("speedtest_uptime_discovered_scatter.pdf")

    ########################
    if GENERATE_EXTRA_PLOTS:
        fig = pyplot.figure()

        sorted_by_before = sorted(data, key=lambda item: item[0])

        uptime = [item[4] for item in sorted_by_before]

        plot_cdf_split(uptime, "Before Rank")

        pyplot.ylabel('CDF')
        pyplot.xlabel('Uptime (\%)')

        pyplot.legend()

        pyplot.tight_layout(pad=0.3)
        pyplot.savefig("speedtest_uptime_rank_before_cdf.pdf")


    ########################
    if GENERATE_EXTRA_PLOTS:
        fig = pyplot.figure()

        sorted_by_after = sorted(data, key=lambda item: item[1])

        uptime = [item[4] for item in sorted_by_after]

        plot_cdf_split(uptime, "After Rank")

        pyplot.ylabel('CDF')
        pyplot.xlabel('Uptime (\%)')

        pyplot.legend()

        pyplot.tight_layout(pad=0.3)
        pyplot.savefig("speedtest_uptime_rank_after_cdf.pdf")


    ########################
    filename = "speedtest_uptime_rank_discovered_cdf.pdf"
    print(f"\n\n########################\n{filename}\n########################")

    fig = pyplot.figure()

    sorted_by_discovered = sorted(data, key=lambda item: item[1]-item[0])
    uptime_sorted_by_discovered = [item[4] for item in sorted_by_discovered]
    discovered_data_range = [item[1]-item[0] for item in sorted_by_discovered]

    plot_cdf_split(uptime_sorted_by_discovered, discovered_data_range, "Abs. Cap. Disc. Rank")

    pyplot.ylabel('CDF')
    pyplot.xlabel('Uptime (\%)')

    pyplot.legend()

    pyplot.tight_layout(pad=0.3)
    pyplot.savefig(filename)


    ########################
    if GENERATE_EXTRA_PLOTS:
        fig = pyplot.figure()
        weight_change = [item[3]-item[2] for item in data]
        discovered = [item[1]-item[0] for item in data]
        pyplot.scatter(discovered, weight_change, s=0.3)

        pyplot.xlabel('Absolute Capacity Discovered (Mbit/s)')
        pyplot.ylabel('Weight Change')

        pyplot.tight_layout(pad=0.3)
        pyplot.savefig("speedtest_weight_discovered_scatter.pdf")

    ########################
    filename = "speedtest_weight_discovered_cdf.pdf"
    print(f"\n\n########################\n{filename}\n########################")

    fig = pyplot.figure()

    sorted_by_discovered = sorted(data, key=lambda item: item[1]-item[0])
    discovered_data_range = [item[1]-item[0] for item in sorted_by_discovered]
    weight_change = [100.0*(item[3]-item[2]) for item in sorted_by_discovered]

    plot_cdf_split(weight_change, discovered_data_range, "Abs. Cap. Disc. Rank")

    pyplot.ylabel('CDF')
    pyplot.xlabel('Absolute Change in Selection Prob. (\%)')

    pyplot.legend()

    pyplot.tight_layout(pad=0.3)
    pyplot.savefig(filename)

    ########################
    filename = "speedtest_weight_discovered_relative_cdf.pdf"
    print(f"\n\n########################\n{filename}\n########################")

    fig = pyplot.figure()

    sorted_by_discovered = sorted(data, key=lambda item: item[1]-item[0])
    discovered_data_range = [item[1]-item[0] for item in sorted_by_discovered]
    weight_change = [100.0*(item[3]-item[2])/item[2] for item in sorted_by_discovered]

    plot_cdf_split(weight_change, discovered_data_range, "Abs. Cap. Disc. Rank")

    pyplot.ylabel('CDF')
    pyplot.xlabel('Relative Change in Selection Prob. (\%)')
    pyplot.xscale('log')

    pyplot.legend()

    pyplot.tight_layout(pad=0.3)
    pyplot.savefig(filename)

    ########################
    if GENERATE_EXTRA_PLOTS:
        fig = pyplot.figure()

        g, m, e = [], [], []
        for item in data:
            before = item[0]
            if item[5] == 'exit':
                e.append(before)
            elif item[5] == 'guard':
                g.append(before)
            elif item[5] == 'middle':
                m.append(before)

        x, y = getcdf(e)
        pyplot.plot(x, y, label="Exit", ls="-")
        x, y = getcdf(g)
        pyplot.plot(x, y, label="Guard", ls="--")
        x, y = getcdf(m)
        pyplot.plot(x, y, label="Middle", ls="-.")

        pyplot.ylabel('CDF')
        pyplot.xlabel('Capacity Before (Mbit/s)')

        pyplot.legend()

        pyplot.tight_layout(pad=0.3)
        pyplot.savefig("speedtest_position_before_cdf.pdf")

    ########################
    filename = "speedtest_position_after_cdf.pdf"
    print(f"\n\n########################\n{filename}\n########################")

    fig = pyplot.figure()

    g, m, e = [], [], []
    for item in data:
        after = item[1]
        if item[5] == 'exit':
            e.append(after)
        elif item[5] == 'guard':
            g.append(after)
        elif item[5] == 'middle':
            m.append(after)

    x, y = getcdf(e)
    pyplot.plot(x, y, label="Exit", ls="-")
    print_stats("Exit CDF:", e)
    x, y = getcdf(g)
    pyplot.plot(x, y, label="Guard", ls="--")
    print_stats("Guard CDF:", g)
    x, y = getcdf(m)
    pyplot.plot(x, y, label="Middle", ls="-.")
    print_stats("Middle CDF:", m)

    pyplot.ylabel('CDF')
    pyplot.xlabel('Absolute Capacity After (Mbit/s)')

    pyplot.legend()

    pyplot.tight_layout(pad=0.3)
    pyplot.savefig(filename)


    ########################
    filename = "speedtest_position_discovered_cdf.pdf"
    print(f"\n\n########################\n{filename}\n########################")

    fig = pyplot.figure()

    g, m, e = [], [], []
    for item in data:
        discovered = item[1]-item[0]
        if item[5] == 'exit':
            e.append(discovered)
        elif item[5] == 'guard':
            g.append(discovered)
        elif item[5] == 'middle':
            m.append(discovered)

    x, y = getcdf(e)
    pyplot.plot(x, y, label="Exit", ls="-")
    print_stats("Exit CDF:", e)
    x, y = getcdf(g)
    pyplot.plot(x, y, label="Guard", ls="--")
    print_stats("Guard CDF:", g)
    x, y = getcdf(m)
    pyplot.plot(x, y, label="Middle", ls="-.")
    print_stats("Middle CDF:", m)

    pyplot.ylabel('CDF')
    pyplot.xlabel('Absolute Capacity Discovered (Mbit/s)')

    pyplot.legend()

    pyplot.tight_layout(pad=0.3)
    pyplot.savefig(filename)


    ########################
    if GENERATE_EXTRA_PLOTS:
        fig = pyplot.figure()

        g, m, e = [], [], []
        for item in data:
            discovered = item[1]-item[0]
            if item[5] == 'exit':
                e.append(discovered)
            elif item[5] == 'guard':
                g.append(discovered)
            elif item[5] == 'middle':
                m.append(discovered)

        x, y = getcdf(e)
        pyplot.plot(x, y, label="Exit", ls="-")
        x, y = getcdf(g)
        pyplot.plot(x, y, label="Guard", ls="--")
        x, y = getcdf(m)
        pyplot.plot(x, y, label="Middle", ls="-.")

        pyplot.ylabel('CDF')
        pyplot.xlabel('Capacity Discovered (Mbit/s)')
        pyplot.xscale('log')

        pyplot.legend()

        pyplot.tight_layout(pad=0.3)
        pyplot.savefig("speedtest_position_discovered_cdf_xlog.pdf")

    ########################
    filename = "speedtest_position_uptime_cdf.pdf"
    print(f"\n\n########################\n{filename}\n########################")

    fig = pyplot.figure()

    a, g, m, e = [], [], [], []
    for item in data:
        uptime = item[4]
        a.append(uptime)
        if item[5] == 'exit':
            e.append(uptime)
        elif item[5] == 'guard':
            g.append(uptime)
        elif item[5] == 'middle':
            m.append(uptime)

    x, y = getcdf(a)
    pyplot.plot(x, y, label="All", ls="-")
    print_stats("All CDF:", a)
    x, y = getcdf(e)
    pyplot.plot(x, y, label="Exit", ls="--")
    print_stats("Exit CDF:", e)
    x, y = getcdf(g)
    pyplot.plot(x, y, label="Guard", ls="-.")
    print_stats("Guard CDF:", g)
    x, y = getcdf(m)
    pyplot.plot(x, y, label="Middle", ls=":")
    print_stats("Middle CDF:", m)

    pyplot.ylabel('CDF')
    pyplot.xlabel('Uptime (\%)')

    pyplot.legend()

    pyplot.tight_layout(pad=0.3)
    pyplot.savefig(filename)

    ########################
    ########################
    ########################
    run_position_plot(data, 'exit')
    run_position_plot(data, 'guard')
    run_position_plot(data, 'middle')
    ########################
    ########################
    ########################


def run_position_plot(data, pos_label):
    ########################
    filename = f"speedtest_{pos_label}_uptime_rank_discovered_cdf.pdf"
    print(f"\n\n########################\n{filename}\n########################")

    fig = pyplot.figure()

    sorted_by_discovered = sorted(data, key=lambda item: item[1]-item[0])
    discovered_data_range = [item[1]-item[0] for item in sorted_by_discovered if item[5] == pos_label]
    uptime = [item[4] for item in sorted_by_discovered if item[5] == pos_label]

    plot_cdf_split(uptime, discovered_data_range, "Abs. Cap. Disc. Rank")

    pyplot.ylabel('CDF')
    pyplot.xlabel('Uptime (\%)')

    pyplot.legend()

    pyplot.tight_layout(pad=0.3)
    pyplot.savefig(filename)

    ########################
    if GENERATE_EXTRA_PLOTS:
        fig = pyplot.figure()

        sorted_by_discovered = sorted(data, key=lambda item: item[1]-item[0])
        after = [item[1] for item in sorted_by_discovered if item[5] == pos_label and item[4] <= 25.0] # "young": uptime < 50%

        plot_cdf_split(after, "Discovered Rank")

        pyplot.ylabel('CDF')
        pyplot.xlabel('Capacity After (Mbit/s)')
        pyplot.xlim(xmax=1000)

        pyplot.legend()

        pyplot.tight_layout(pad=0.3)
        pyplot.savefig(f"speedtest_{pos_label}young_after_rank_discovered_cdf.pdf")

    ########################
    filename = f"speedtest_{pos_label}old_after_rank_discovered_cdf.pdf"
    print(f"\n\n########################\n{filename}\n########################")

    fig = pyplot.figure()

    sorted_by_discovered = sorted(data, key=lambda item: item[1]-item[0])
    discovered_data_range = [item[1]-item[0] for item in sorted_by_discovered if item[5] == pos_label and item[4] >= 75.0]
    after = [item[1] for item in sorted_by_discovered if item[5] == pos_label and item[4] >= 75.0] # "old": uptime > 50%

    plot_cdf_split(after, discovered_data_range, "Abs. Cap. Disc. Rank")

    pyplot.ylabel('CDF')
    pyplot.xlabel('Absolute Capacity After (Mbit/s)')
    pyplot.xlim(xmax=1000)

    pyplot.legend()

    pyplot.tight_layout(pad=0.3)
    pyplot.savefig(filename)

    ########################
    filename = f"speedtest_{pos_label}old_after_rank_reldiscovered_cdf.pdf"
    print(f"\n\n########################\n{filename}\n########################")

    fig = pyplot.figure()

    sorted_by_reldiscovered = sorted(data, key=lambda item: 100.0*(item[1]-item[0])/item[1])
    reldiscovered_data_range = [100.0*(item[1]-item[0])/item[1] for item in sorted_by_reldiscovered if item[5] == pos_label and item[4] >= 75.0]
    after = [item[1] for item in sorted_by_reldiscovered if item[5] == pos_label and item[4] >= 75.0] # "old": uptime > 50%

    plot_cdf_split(after, reldiscovered_data_range, "Rel. Cap. Disc. Rank")

    pyplot.ylabel('CDF')
    pyplot.xlabel('Absolute Capacity After (Mbit/s)')
    pyplot.xlim(xmax=1000)

    pyplot.legend()

    pyplot.tight_layout(pad=0.3)
    pyplot.savefig(filename)

def plot_cdf_split(data, ranked_data, label_prefix):
    data_len = int(len(data)/4.0)

    p25_index, p50_index, p75_index = data_len, 2*data_len, 3*data_len

    print("{} data range:\n\tmin: {}\n\t25%: {}\n\t50%: {}\n\t75%: {}\n\tmax: {}".format(label_prefix, ranked_data[0], ranked_data[p25_index], ranked_data[p50_index], ranked_data[p75_index], ranked_data[-1]))

    x, y = getcdf(data[0:p25_index])
    label = f"{label_prefix} [0\%,25\%)"
    pyplot.plot(x, y, label=label, ls="-")
    print_stats(f"CDF stat summary: {label}", data[0:p25_index])

    x, y = getcdf(data[p25_index:p50_index])
    label = f"{label_prefix} [25\%,50\%)"
    pyplot.plot(x, y, label=label, ls="--")
    print_stats("CDF stat summary: "+label, data[p25_index:p50_index])

    x, y = getcdf(data[p50_index:p75_index])
    label = f"{label_prefix} [50\%,75\%)"
    pyplot.plot(x, y, label=label, ls="-.")
    print_stats("CDF stat summary: "+label, data[p50_index:p75_index])

    x, y = getcdf(data[p75_index:])
    label = f"{label_prefix} [75\%,100\%]"
    pyplot.plot(x, y, label=label, ls=":")
    print_stats("CDF stat summary: "+label, data[p75_index:])

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
        'legend.fontsize' : 6,
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
