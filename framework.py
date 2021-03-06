# FFW - Fuzzing For Worms
# Author: Dobin Rutishauser
#
# Parts of it based on:
#   Framework for fuzzing things
#   author: Chris Bisnett

import logging
import argparse
import os
import glob

from network import replay
from network import interceptor
from fuzzer import fuzzingmaster
from verifier import verifier
from verifier import minimizer
from uploader import uploader
from network import tester
from network import proto_vnc
from honggmode import honggmode


def checkRequirements(config):
    if not os.path.isfile(config["target_bin"]):
        print "Target binary not found: " + str(config["target_bin"])
        return False

    return True


def checkFuzzRequirements(config):
    f = config["projdir"] + '/in/*.pickle'
    if len( glob.glob(f)) <= 0:
        print "No intercepted data found: " + str(f)
        return False

    return True


def realMain(config):
    parser = argparse.ArgumentParser("Fuzzing For Worms")

    group = parser.add_mutually_exclusive_group()
    group.add_argument('--intercept', help='Intercept and record network communication', action="store_true")
    group.add_argument('--test', help='Test intercepted network communication', action="store_true")
    group.add_argument('--fuzz', help='Perform fuzzing', action="store_true")
    group.add_argument('--honggmode', help='Perform honggfuze based fuzzing', action="store_true")
    group.add_argument('--verify', help='Verify crashes', action="store_true")
    group.add_argument('--minimize', help='Minimize crashes', action="store_true")
    group.add_argument('--replay', help='Replay a crash', action="store_true")
    group.add_argument('--upload', help='Upload verified crashes', action="store_true")

    parser.add_argument('--debug', help="More error messages, only one process", action="store_true")
    parser.add_argument('--gui', help='Fuzzer: Use ncurses gui', action="store_true")
    parser.add_argument('--processes', help='Fuzzer: How many paralell processes', type=int)

    # TODO: make this mode specific
    parser.add_argument("--honggcov", help="Select Honggfuzz coverage: hw/sw", default="sw")
    parser.add_argument('--listenport', help='Intercept: Listener port', type=int)
    parser.add_argument('--targetport', help='Intercept/Replay: Port to be used for the target server', type=int)
    parser.add_argument('--file', help="Verify/Replay: Specify file to be used")
    parser.add_argument('--url', help="Uploader: url")
    parser.add_argument('--basic_auth_user', help='Uploader: basic auth user')
    parser.add_argument('--basic_auth_password', help='Uploader: basic auth password')
    args = parser.parse_args()

    if not checkRequirements(config):
        print "Requirements not met."
        return

    # TODO remove this from here
    if config["proto"] == "vnc":
        print("Using protocol: vnc")
        config["protoObj"] = proto_vnc.ProtoVnc()
    else:
        config["protoObj"] = None

    if args.processes:
        config["processes"] = args.processes

    if args.debug:
        logging.basicConfig(level=logging.DEBUG)
        config["processes"] = 1
        config["debug"] = True
    else:
        config["debug"] = False

    if args.intercept:
        interceptorPort = 10000
        targetPort = 20000

        if args.listenport:
            interceptorPort = args.listenport

        if args.targetport:
            targetPort = args.targetport

        print("Interceptor listen on port: " + str(interceptorPort))
        print("Target port: " + str(targetPort))

        interceptor.doIntercept(config, interceptorPort, targetPort)


    if args.test:
        t = tester.Tester(config)
        t.test()

    if args.fuzz:
        if not checkFuzzRequirements(config):
            return False
        fuzzingmaster.doFuzz(config, args.gui)

    if args.honggmode:
        if not checkFuzzRequirements(config):
            return False

        if args.honggcov == "hw" or config["honggcov"] == "hw":
            config["honggmode_option"] = "--linux_perf_bts_edge"

            if os.geteuid() != 0:
                logging.error("--honggcov hw hardware coverage requires root")
                return
        elif args.honggcov == "sw" or config["honggcov"] == "sw":
            config["honggmode_option"] = None  # sw is default
        else:
            config["honggmode_option"] = None

        honggmode.doFuzz(config)

    if args.verify:
        v = verifier.Verifier(config)

        if args.file:
            v.verifyFile(args.file)
        else:
            v.verifyOutDir()

    if args.minimize:
        mini = minimizer.Minimizer(config)
        mini.minimizeOutDir()

    if args.replay:
        replayer = replay.Replayer(config)

        if not args.file:
            print "Use --file to specify a file to be replayed"
        elif not args.targetport:
            print "Use --targetport to specify port to send data to"
        else:
            replayer.replayFile(args.targetport, args.file)

    if args.upload:
        if args.basic_auth_user and args.basic_auth_password:
            u = uploader.Uploader(config, args.url, args.basic_auth_user, args.basic_auth_password)
        else:
            u = uploader.Uploader(config, args.url, None, None)

        u.uploadVerifyDir()
