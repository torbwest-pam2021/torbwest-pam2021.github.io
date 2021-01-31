#!/usr/bin/env python36

import sys
import os
import argparse
import time
import datetime
import logging
import json

from threading import Lock

from functools import partial

from stem.control import EventType, Controller
from stem.descriptor import parse_file

DESCRIPTION="""
This utility is used to control a set of Tor clients to run a speedtest on all relays
in the Tor network. The client builds two-relay circuits, where the first relay is
the speedtest target and the second relay is a speedtest support relay. The Tor clients
and the speedtest support relays must run a custom speedtest branch of Tor:
https://github.com/robgjansen/tor/tree/research/speedtest/v1-squashed
"""

"""
You must define here the information for the client and relay pairs that you set up
that should be used to conduct the speed test. The number in the clients dict (e.g., 9090)
is the control port of the Tor client running on the machine, and the corresponding
fingerprint (e.g., 70AB9FC42C2FE750B24EECD27F7C25139F01EB6C) is the Tor relay that the
client will use as the second hop in the speed test circuits. These relays should be
regular Tor relays. You may want to set the MaxAdvertisedBandwidth torrc option on
your relays so they don't attract too much regular client traffic during the experiment.

Here we used 10 clients with control ports 9090-9099 and 10 assoicated relays. All of
these nodes run the Tor branch from
https://github.com/robgjansen/tor/tree/research/speedtest/v1-squashed
"""
STATE = {
    'round': 1,
    'num_measurements': 0,
    'target_fp': '',
    'clients': {
        9090: {'helper': {'nickname': 'SpeedTest0', 'fingerprint': '70AB9FC42C2FE750B24EECD27F7C25139F01EB6C'}},
        9091: {'helper': {'nickname': 'SpeedTest1', 'fingerprint': '244FA0202C1C0614348A083CC30413C1CCBB76BC'}},
        9092: {'helper': {'nickname': 'SpeedTest2', 'fingerprint': 'BD371C3DAA20B6F844A520F91360BF6F9697A35A'}},
        9093: {'helper': {'nickname': 'SpeedTest3', 'fingerprint': 'A0A4B07A3AB0DD3D10E2C3C98972828F84BE78AB'}},
        9094: {'helper': {'nickname': 'SpeedTest4', 'fingerprint': '702FF3F56721FF45AB148C97DB5B7D10C72BE9CF'}},
        9095: {'helper': {'nickname': 'SpeedTest5', 'fingerprint': 'E2BA3220F0863AFF34D3BFE36B653CC5CDC3F825'}},
        9096: {'helper': {'nickname': 'SpeedTest6', 'fingerprint': '96BE33F702C9D15CA374CD2041000987771C082C'}},
        9097: {'helper': {'nickname': 'SpeedTest7', 'fingerprint': '45E702D042C84D7A7C63310940161E293C6E5CEF'}},
        9098: {'helper': {'nickname': 'SpeedTest8', 'fingerprint': '50E874B35119FB516A1098BFE132ACFA6164AC3E'}},
        9099: {'helper': {'nickname': 'SpeedTest9', 'fingerprint': 'D3E6CFAB65F29FE9450707C96BA45F2FE90F6B85'}},
    },
    'relays': {

    }
}

CONTROLLERS = {}

# If you want to conduct a small test rather than measuring the entire network,
# define a set of fingerprints here for those relays you want to measure.
TEST_TARGET_RELAYS = set([])
#TEST_TARGET_RELAYS = set([
#    '2767A9DB46503D09FD0415BA1296B36318520F08', # TFinn1
#    '643E0E402A0E9341D5FACEC4D3149E1F3AB6B345', # TFinn2
#    '859A5CE99951A3C42958AF88CE2761BD48525B16', # TFinn3
#    'BFC1F28F0D34B71F535A38F1E25CF03A3FD9EAA1', # TFinn4
#])

# These relays will never be measured
RELAY_BLACKLIST = set([])

# Length of time to send a burst of traffic through each relay, in seconds.
SPEEDTEST_LENGTH = 20

EVENT_LOCK = Lock()

def main():
    # construct the options
    parser = argparse.ArgumentParser(
        description=DESCRIPTION,
        formatter_class=argparse.ArgumentDefaultsHelpFormatter) # RawTextHelpFormatter

    parser.add_argument('-l', '--logpath',
        help="""a STRING path to log Tor controller output""",
        action="store", type=str, metavar="STRING",
        dest="logpath", default="{}/{}".format(os.getcwd(), "speedtester.log"))

    parser.add_argument('-s', '--statepath',
        help="""a STRING path to store speedtest state""",
        action="store", type=str, metavar="STRING",
        dest="statepath", default="{}/{}".format(os.getcwd(), "speedtester.state"))

    args = parser.parse_args()
    args.statepath = os.path.abspath(os.path.expanduser(args.statepath))
    args.logpath = os.path.abspath(os.path.expanduser(args.logpath))
    setup_logging(args.logpath)
    run(args)

def run(args):
    global STATE
    if os.path.exists(args.statepath):
        with open(args.statepath, 'r') as statefile:
            STATE = json.load(statefile)

    STATE['target_fp'] = ''

    logging.info("Starting control of {} Tor clients".format(len(STATE['clients'])))
    for ctrl_port in STATE['clients']:
        STATE['clients'][ctrl_port]['status'] = 'IDLE'
        STATE['clients'][ctrl_port]['circid'] = 0
        setup_controller(ctrl_port)

    # let stem run its threads and log all of the events, until user interrupts
    try:
        while True:
            EVENT_LOCK.acquire()
            targets, num_total = get_relays(args)
            EVENT_LOCK.release()

            msg = "heartbeat: performed {} measurements, {}/{} relays remain in round {}, press CTRL-C to quit".format(STATE['num_measurements'], len(targets), num_total, STATE['round'])

            logging.info(msg)

            endtime = time.time() + 60.0
            while time.time() < endtime:
                EVENT_LOCK.acquire()
                run_one_second_loop(targets)
                EVENT_LOCK.release()
                time.sleep(1)
    except KeyboardInterrupt:
        logging.info("Caught a KeyboardInterrupt from user")
        pass  # the user hit ctrl+c

    logging.info("Shutting down {} controllers...".format(len(STATE['clients'])))
    for ctrl_port in STATE['clients']:
        if 'circid' in STATE['clients'][ctrl_port] and STATE['clients'][ctrl_port]['circid'] > 0:
            status = STATE['clients'][ctrl_port]['status']
            if status == "STARTING" or status == "STARTED":
                send_stop(ctrl_port)
                send_close(ctrl_port)
            elif status != "CLOSING" and status != "CLOSED":
                send_close(ctrl_port)
        shutdown_controller(ctrl_port)
    get_relays(args)
    logging.info("Done, goodbye!")

def run_one_second_loop(targets):
    n_clients = len(STATE['clients'])
    status_counts, str_counts = count_status()
    logging.info("Client status counts: {}".format(str_counts))

    if status_counts['IDLE'] + status_counts['CLOSED'] == n_clients:
        logging.info("All clients are IDLE!")
        if len(targets) > 0:
            logging.info("Sending open to {} clients now".format(len(STATE['clients'])))
            STATE['target_fp'] = targets.pop()
            for ctrl_port in STATE['clients']:
                send_open(ctrl_port, STATE['target_fp'])

    elif status_counts['OPENED'] == n_clients:
        logging.info("All clients are OPENED!")
        logging.info("Sending start to {} clients now".format(len(STATE['clients'])))
        for ctrl_port in STATE['clients']:
            send_start(ctrl_port, SPEEDTEST_LENGTH)

    elif status_counts['STARTED'] == n_clients:
        logging.info("All clients are STARTED!")

    elif status_counts['STOPPED'] == n_clients:
        logging.info("All clients are STOPPED!")
        logging.info("Sending close to {} clients now".format(len(STATE['clients'])))
        for ctrl_port in STATE['clients']:
            send_close(ctrl_port)
        STATE['num_measurements'] += 1
        if STATE['target_fp'] in STATE['relays']:
            fp = STATE['target_fp']
            STATE['relays'][fp]['n_measured'] = int(STATE['relays'][fp]['n_measured']) + 1
        STATE['target_fp'] = ''

    elif status_counts['CLOSED'] == n_clients:
        logging.info("All clients are CLOSED!")
        for ctrl_port in STATE['clients']:
            if 'circid' in STATE['clients'][ctrl_port]:
                STATE['clients'][ctrl_port]['circid'] = 0
            set_status(ctrl_port, 'IDLE')

    else:
        target_fp = STATE['target_fp']
        now = time.time()
        did_timeout = False
        for ctrl_port in STATE['clients']:
            status = STATE['clients'][ctrl_port]['status']
            status_ts = float(STATE['clients'][ctrl_port]['status_ts'])
            circid = int(STATE['clients'][ctrl_port]['circid'])
            if now - status_ts > 30.0:
                set_status(ctrl_port, 'IDLE')
                STATE['clients'][ctrl_port]['circid'] = 0
            elif now - status_ts > 25.0:
                did_timeout = True
                if circid > 0:
                    if status == 'STARTING' or status == "STARTED":
                        send_stop(ctrl_port)
                    elif status != 'CLOSING' and status != "CLOSED":
                        send_close(ctrl_port)
                else:
                    set_status(ctrl_port, 'IDLE')
        if did_timeout and target_fp in STATE['relays']:
            STATE['relays'][target_fp]['n_timeouts'] = int(STATE['relays'][target_fp]['n_timeouts']) + 1
            STATE['target_fp'] = ''

def count_status():
    counts = {'IDLE':0, 'OPENING':0, 'OPENED':0, 'STARTING':0, 'STARTED':0, 'STOPPING':0, 'STOPPED':0, 'CLOSING':0, 'CLOSED':0}
    for ctrl_port in STATE['clients']:
        status = STATE['clients'][ctrl_port]['status']
        counts.setdefault(status, 0)
        counts[status] += 1
    str_counts = {}
    for c in counts:
        if counts[c] > 0:
            str_counts[c] = counts[c]
    return counts, str_counts

def set_status(ctrl_port, status):
    STATE['clients'][ctrl_port]['status'] = status
    STATE['clients'][ctrl_port]['status_ts'] = time.time()

def send_stop(ctrl_port):
    msg = "SPEEDTEST STOP {}".format(STATE['clients'][ctrl_port]['circid'])
    send_message(ctrl_port, msg)
    set_status(ctrl_port, "STOPPING")

def send_start(ctrl_port, seconds):
    msg = "SPEEDTEST START {} {}".format(STATE['clients'][ctrl_port]['circid'], seconds)
    send_message(ctrl_port, msg)
    set_status(ctrl_port, "STARTING")

def send_close(ctrl_port):
    msg = "SPEEDTEST CLOSE {}".format(STATE['clients'][ctrl_port]['circid'])
    send_message(ctrl_port, msg)
    set_status(ctrl_port, "CLOSING")

def send_open(ctrl_port, target_fp):
    helper_fp = STATE['clients'][ctrl_port]['helper']['fingerprint']
    path = "{},{}".format(target_fp, helper_fp)
    msg = "SPEEDTEST OPEN {}".format(path)
    send_message(ctrl_port, msg)
    set_status(ctrl_port, "OPENING")

def send_message(ctrl_port, msg):
    CONTROLLERS[ctrl_port].get_socket().send(msg)
    logging.info("{}: command '{}'".format(ctrl_port, msg))

def get_relays(args):
    logging.info("Getting relay information from cached consensus")

    current_relays = set()
    for desc in parse_file('/home/rjansen/run/speedtest0/cached-consensus'):
        nn, fp, bw = desc.nickname, desc.fingerprint, desc.bandwidth
        if len(TEST_TARGET_RELAYS) > 0 and fp not in TEST_TARGET_RELAYS: continue
        if fp in RELAY_BLACKLIST: continue
        current_relays.add(fp)
        if fp not in STATE['relays']:
            STATE['relays'][fp] = {'n_measured': 0, 'n_timeouts':0, 'nickname': nn, 'bandwidth': bw}
        else:
            STATE['relays'][fp]['bandwidth'] = bw

    targets = {}
    for fp in current_relays:
        n_tries = int(STATE['relays'][fp]['n_measured']) + int(STATE['relays'][fp]['n_timeouts'])
        if n_tries < int(STATE['round']) and fp != STATE['target_fp']:
            targets[fp] = STATE['relays'][fp]['bandwidth']

    if len(targets) <= 0:
        # we tried everyone once. go back and retry the timeouts
        for fp in current_relays:
            if int(STATE['relays'][fp]['n_measured']) < int(STATE['round']):
                targets[fp] = STATE['relays'][fp]['bandwidth']

    num_total = len(current_relays)

    with open(args.statepath, 'w') as statefile:
        json.dump(STATE, statefile, indent=2)

    sorted_target_fps = [item[0] for item in sorted(targets.items(), key=lambda kv: kv[1])]

    return sorted_target_fps, num_total

def shutdown_controller(ctrl_port):
    #STATE[ctrl_port]['controller'].remove_event_listener(__handle_async_event)
    CONTROLLERS[ctrl_port].close()

def setup_controller(ctrl_port):
    CONTROLLERS[ctrl_port] = Controller.from_port(port=int(ctrl_port))
    CONTROLLERS[ctrl_port].authenticate()

    # register for async events
    event_handler = partial(__handle_async_event, ctrl_port, )

    try:
        CONTROLLERS[ctrl_port].add_event_listener(event_handler, EventType.BW)
    except:
        logging.warning("event 'BW' is recognized by stem but not by tor")

    try:
        CONTROLLERS[ctrl_port].add_event_listener(event_handler, 'SPEEDTEST')
    except:
        logging.error("event 'SPEEDTEST' is not recognized by tor, cannot continue")
        return

def __handle_async_event(ctrl_port, event):
    EVENT_LOCK.acquire()
    event_str = event.raw_content().rstrip('\r\n')
    msg = "{}: {}".format(ctrl_port, event_str)

    logging.info(msg)

    parts = event_str.split()
    if parts[0] == "650":
        if parts[1] == "SPEEDTEST":
            circid = int(parts[3])

            if parts[2] == "OPENED":
                if STATE['clients'][ctrl_port]['status'] == 'OPENING':
                    set_status(ctrl_port, 'OPENED')
                    STATE['clients'][ctrl_port]['circid'] = circid
            elif parts[2] == "STARTED":
                if circid == int(STATE['clients'][ctrl_port]['circid']):
                    set_status(ctrl_port, 'STARTED')
            elif parts[2] == "STOPPED":
                if circid == int(STATE['clients'][ctrl_port]['circid']):
                    set_status(ctrl_port, 'STOPPED')
            elif parts[2] == "CLOSED":
                if circid == int(STATE['clients'][ctrl_port]['circid']):
                    set_status(ctrl_port, 'CLOSED')
                    STATE['clients'][ctrl_port]['circid'] = 0
    EVENT_LOCK.release()

def setup_logging(logfilename):
    file_handler = logging.FileHandler(filename=logfilename)
    stdout_handler = logging.StreamHandler(sys.stdout)

    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s %(created)f [tor-speedtester] [%(levelname)s] %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S',
        handlers=[file_handler, stdout_handler],
    )

    logging.info("Logging system initialized! Logging events to stdout and to '{}'".format(logfilename))

if __name__ == '__main__': sys.exit(main())
