### Overview

This page provides instructions for reproducing our relay speed test analysis. See [the front page](/) for more context.

The speed test itself was run on the Tor network using some changes to Tor and a python controller script as discussed in the paper. Here are the components that we used when running the speed test.

- [Post to tor-relays mailing list explaining the experiment](https://lists.torproject.org/pipermail/tor-relays/2019-July/017535.html)
- [Tor code branch implementing speed test support](https://github.com/robgjansen/tor/tree/research/speedtest/v1-squashed)
- [Script for running the actual speed test](speedtester.py)

The results are stored in [speedtester.json.xz](speedtester.json.xz) and are used in the analysis below, wherein we attempt to better understand the effects of the speed test.

**Note:** the data processing tasks in Steps 1-4 have already been done, and the output from those steps have been cached in this repository. If you just want to re-plot the graphs, do Step 0 and then skip to Step 5.

### Step 0: prepare python virtual environment

    python3 -m venv myenv
    source myenv/bin/activate
    pip3 install stem matplotlib numpy scipy

### Step 1: download raw Tor metrics data

    wget https://collector.torproject.org/archive/relay-descriptors/server-descriptors/server-descriptors-2019-08.tar.xz
    wget https://collector.torproject.org/archive/relay-descriptors/consensuses/consensuses-2019-08.tar.xz

### Step 2: decompress

    tar xJf server-descriptors-2019-08.tar.xz
    tar xJf consensuses-2019-08.tar.xz

### Step 3: extract bandwidth info

    source myenv/bin/activate

    # output is tor.archive.json
    python3 parse_tor_archive.py consensuses-2019-08 server-descriptors-2019-08

### Step 4: compute

    source myenv/bin/activate

    # input is speedtester.json.xz, output is speedtest.measured.json.xz
    python3 parse_measured.py

    # input is speedtest.measured.json.xz and tor.archive.json
    # output is speedtest.diffs.json.xz and advbw_over_time.json.xz
    python3 process_speedtest.py

### Step 5: plot the graphs

    source myenv/bin/activate

    # input is advbw_over_time.json.xz
    python3 plot_speedtest_timeseries.py > stats_timeseries.txt

    # input is speedtest.measured.json.xz, speedtest.diffs.json.xz,
    # ../capacity_variation/relay_uptime.json.xz, and
    # ../capacity_variation/relay_position.json.xz
    python3 plot_speedtest_explore.py > stats_explore.txt

### Results

- Main body Figures [2a](speedtest-timeseries.pdf), [2b](speedtest_change_mbit_scatter.pdf), [3a](speedtest_rank_discovered_plot.pdf), [3b](speedtest_perc_discovered_cdf.pdf), [4a](speedtest_position_after_cdf.pdf), [4b](speedtest_position_discovered_cdf.pdf), [5a](speedtest_uptime_rank_discovered_cdf.pdf), [5b](speedtest_exitold_after_rank_reldiscovered_cdf.pdf), [6a](speedtest_weight_discovered_cdf.pdf), [6b](speedtest_weight_discovered_relative_cdf.pdf).
- Appendix Figures [7a](speedtest_exit_uptime_rank_discovered_cdf.pdf), [7b](speedtest_guard_uptime_rank_discovered_cdf.pdf), [7c](speedtest_middle_uptime_rank_discovered_cdf.pdf), [8a](speedtest_guardold_after_rank_reldiscovered_cdf.pdf), [8b](speedtest_middleold_after_rank_reldiscovered_cdf.pdf), [9a](speedtest_exitold_after_rank_discovered_cdf.pdf), [9b](speedtest_guardold_after_rank_discovered_cdf.pdf), [9c](speedtest_middleold_after_rank_discovered_cdf.pdf)
- [Statistics](stats_timeseries.txt) for Figure 2a
- [Statistics](stats_explore.txt) for other figures
