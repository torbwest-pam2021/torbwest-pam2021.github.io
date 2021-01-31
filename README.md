### Overview

This is the landing page for the following research publication:

**On the Accuracy of Tor Bandwidth Estimation**  
_Proceedings of the 22nd Passive and Active Measurement Conference (PAM 2021)_  
by [Rob Jansen](https://www.robgjansen.com) and [Aaron Johnson](https://ohmygodel.com)  
\[[Full paper available here](https://www.robgjansen.com/publications/torbwest-pam2021.pdf)\]

If you reference this paper or use any of the data provided on this page, please cite the paper. Here is a bibtex entry for latex users:

```
@inproceedings{torbwest-pam2021,
author = {Rob Jansen and Aaron Johnson},
title = {On the Accuracy of {Tor} Bandwidth Estimation},
booktitle = {22nd Passive and Active Measurement Conference (PAM)},
year = {2021},
note = {See also \url{https://torbwest-pam2021.github.io}},
}
```

The research included an analysis of Tor relay capacity variation component, and a Tor relay speed test experiment and analysis component.


### Tor Relay Capacity Variation

We analyzed Tor network consensus and relay server descriptor files to understand the variation in relays' advertised bandwidths. More information about reproducing the analysis and graphs (in Figure 1 in the paper) is available [here](capacity_variation/).


### Tor Relay Speed Test

We conducted a Tor relay speed test wherein we attempted to drive 1 Gbit/s of traffic through each relay in order to cause them to detect their available bandwidth capacity. More information about running the test, and about reproducing the analysis and graphs (everything except Figure 1 in the paper) is available [here](speed_test/).
