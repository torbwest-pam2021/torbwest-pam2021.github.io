### Overview

This page provides instructions for reproducing our relay capacity variation analysis. See [the front page](/) for more context.

**Note:** the data processing tasks in Steps 1-4 have already been done, and the output from those steps have been cached in this repository. If you just want to re-plot the graphs, do Step 0 and then skip to Step 5.

### Step 0: prepare python virtual environment

    python3 -m venv myenv
    source myenv/bin/activate
    pip3 install stem matplotlib numpy scipy

### Step 1: download raw Tor metrics data

    for d in 2018-08 2018-09 2018-10 2018-11 2018-12 2019-01 2019-02 2019-03 2019-04 2019-05 2019-06 2019-07
    do
        wget https://collector.torproject.org/archive/relay-descriptors/server-descriptors/server-descriptors-${d}.tar.xz
        wget https://collector.torproject.org/archive/relay-descriptors/consensuses/consensuses-${d}.tar.xz
    done

### Step 2: decompress

    tar xJf *tar.xz
    mkdir cons
    mv consensuses* cons
    mkdir sdesc
    mv server-desc* sdesc

### Step 3: extract bandwidth info

    source myenv/bin/activate
    python3 parse_tor_archive.py cons sdesc

### Step 4: compute

    source myenv/bin/activate

    # input for all scripts is the tor.archive.json file created in Step 3

    # these metrics are computed over all data throughout the entire year
    python3 compute_position.py
    python3 compute_uptime.py
    python3 compute_weight.py
    python3 compute_advbw.py

    # compute relative standard deviation while ignoring unmeasured relays
    # and weeks where bwrate or bwburst changed advertised bandwidth
    python3 compute_rsds.py

### Step 5: plot the graphs

    # uses the output from Steps 3 and 4
    source myenv/bin/activate
    python3 plot_rsds.py > stats.txt

### Results

Figures [1a](capacity_rsds_position_cdf.pdf), [1b](capacity_rsds_uptime_cdf.pdf), [1c](capacity_rsds_advbw_cdf.pdf), and [1d](capacity_rsds_weight_cdf.pdf); and related [statistics](stats.txt)
