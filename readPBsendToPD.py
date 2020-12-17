#!/usr/bin/python3
# -*- coding: utf8 -*-
#####################################################################
# readPBsendToPD.py
# Read bluetooth keyboad and send red keys to PD over UDP
######################################################################
import socket
import evdev
import time
import sys
import traceback
import termios
import tty
from sys import stdin
from collections import deque
import itertools
from time import perf_counter
from pythonosc.udp_client import SimpleUDPClient
import logging
import argparse

OSC_SEND_MSG = {'CONNECT':'/Connexion/value','TEMPO':'/Tempo/value'}
WAIT = 3
RETRY = 2400 ## Deux heures
FOOTBOARD = "Adafruit EZ-Key 6baa Keyboard"

KEY_NAMES = {"MUTE_ALL":"0","UNMUTE_ALL":"1","START_STOP":"5","TAP_TEMPO":"9","NEXT_PGM":".","PREV_PGM":"<"}
CTRL_KEYS = {82:"MUTE_ALL",79:"UNMUTE_ALL",76:"START_STOP",73:"TAP_TEMPO",83:"NEXT_PGM",86:"PREV_PGM"}

def getchar():
    fd = stdin.fileno()
    old_settings = termios.tcgetattr(fd)
    try:
        tty.setraw(stdin.fileno())
        ch = stdin.read(1)
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
    return ch

def send_osc(msg=None, value=None, oscclient=None):
    if oscclient is not None:
        oscclient.send_message(OSC_SEND_MSG[msg], value)


def discoverPedalBoard(footboard=None,wait=10,retry=10,oscclient=None):

    send_osc(msg="CONNECT", value="Discover BT", oscclient=oscclient)
    logging.info('Discovering BT devices ...')
    footdev = None
    dev = None
    tried = 0

    while footdev is None:
        devices = evdev.list_devices()
        for d in devices:
            dev = evdev.InputDevice(d)
            if dev.name == footboard:
                logging.info('Device found : %s' % footboard)
                send_osc(msg="CONNECT", value="Found %s" % footboard , oscclient=oscclient)
                footdev = d
                return (footdev,dev)
            else:
                logging.debug('try # %s ' % tried)
                time.sleep(wait)
                tried += 1
                if tried >= retry:
                    return (footdev,dev)
        time.sleep(3)


def averagetimes(tap):
    '''
    Compute average time of the last 4 taps
    '''
    averagetime = sum([row for row in tap]) / float(len(tap))
    bpm = (1.0 / (averagetime / 60.0))
    return (averagetime, bpm)


def readPedalBoard(dev=None,hostpd=None,portkey=None,porttap=None,oscclient=None):
    logging.info('Reading Pedal Board')
    tap = deque()
    elapse = None
    prevelapse = None
    mean = None

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

    try:
        for event in dev.read_loop():
            if event.type == evdev.ecodes.EV_KEY:
                logging.debug('Get : %s' % evdev.categorize(event))
                evdev.ecodes.KEY[30]
                if event.value == 1:
                    if dev.active_keys()[0] in CTRL_KEYS:
                        logging.debug('Get %s ' % CTRL_KEYS[dev.active_keys()[0]])
                        if CTRL_KEYS[dev.active_keys()[0]] == "TAP_TEMPO":
                            if prevelapse is None:
                                prevelapse = perf_counter()
                            else:
                                elapse = perf_counter()
                                ms = elapse - prevelapse
                                prevelapse = elapse
                                tap.append(ms)

                            if len(tap) >= 3:
                                averagetime, bpm = averagetimes(tap)
                                clockvalue = '%.4d' % int(averagetime*1000)
                                logging.debug('Clock Value :%s, BPM : %s' % (clockvalue,int(bpm)))
                                try:
                                    send_osc(msg="TEMPO", value=int(bpm) , oscclient=oscclient)
                                except:
                                    E=traceback.format_exception(sys.exc_info()[0], sys.exc_info()[1], sys.exc_info()[2])
                                    logging.error(E)
                                sock.sendto(bytes(clockvalue,"utf8"), (hostpd,porttap))
                                tap.popleft()
                        else:
                            if CTRL_KEYS[dev.active_keys()[0]] == "START_STOP":
                                tap = deque()
                                elapse = None
                                prevelapse = None
                                mean = None
                            sock.sendto(bytes(KEY_NAMES[CTRL_KEYS[dev.active_keys()[0]]], "utf-8"), (hostpd,portkey))

    except (KeyboardInterrupt, SystemExit):
            logging.info("Shutdown from readPedalBoard ...")
            return 99
    except (OSError) as err:
        logging.error(err)
        return -2
    except:
        E=traceback.format_exception(sys.exc_info()[0], sys.exc_info()[1], sys.exc_info()[2])
        logging.error(E)
        sock.close()
        return -1

def msg():
    return '''%s
        -h, help
        -pdadd      Adresse pure data (defaut 127.0.0.1)
        -pdtapport  Port pure data tap tempo (defaut 50001)
        -pdkeyport  Port pure data keys (defaut 50001)
        -ipadadd    Adresse IP Ipad (defaut 192.168.0.5)
        -ipadport   Port OSC IPAD (defaut 8000)
        -loglevel   niveau de log [DEBUG,ERROR,WARNING,INFO]
        '''%sys.argv[0]

def decodeArgs():
    '''
    Decodage des arguments
    '''

    parser = argparse.ArgumentParser(description='read X18, send to Ipad', usage=msg())
    #parser.add_argument('-h', '--help', help='help',const='HELP',nargs='?')
    parser.add_argument('-pdadd', help="Adresse pure data (defaut 127.0.0.1)", default="127.0.0.1")
    parser.add_argument('-pdtapport', help="Port pure data tap tempo (defaut 50001)",default=50001)
    parser.add_argument('-pdkeyport', help="Port pure data keys (defaut 50001)",default=50000)
    parser.add_argument('-ipadadd', help="Adresse IP Ipad (defaut 192.168.0.5)",default='192.168.0.5')
    parser.add_argument('-ipadport', help="Port OSC IPAD (defaut 8000)",default=8000)
    parser.add_argument('-loglevel', help="niveau de log [DEBUG,ERROR,WARNING,INFO]",default='INFO')
    return parser.parse_args()

def main():
    arg_analyze=decodeArgs()
    PD_IP = arg_analyze.pdadd
    PD_PORT_KEYS = arg_analyze.pdkeyport
    PD_PORT_TAP =  arg_analyze.pdtapport

    IPAD_IP = arg_analyze.ipadadd
    IPAD_OSC_PORT = arg_analyze.ipadport
    loglevel = arg_analyze.loglevel

    logging.basicConfig(level=loglevel, format='%(asctime)s - %(levelname)s - readPBSendToPD : %(message)s', datefmt='%Y%m%d%I%M%S ')

    oscclient = None
    try:
        oscclient = SimpleUDPClient(IPAD_IP, IPAD_OSC_PORT)
    except:
        E=traceback.format_exception(sys.exc_info()[0], sys.exc_info()[1], sys.exc_info()[2])
        logging.error(E)

    retry = RETRY
    E = None
    while retry > 0:
        try:
            oscclient.send_message('/Connexion/value', 'Connected')
            break
        except:
            E=traceback.format_exception(sys.exc_info()[0], sys.exc_info()[1], sys.exc_info()[2])
            retry -= 1
            time.sleep(WAIT)

    if retry <= 0:
        logging.error("cannot connect to IPAD %s" % E)
        exit(-1)
    else:
        logging.info('Connected to IPAD')


    retry = RETRY
    while retry > 0:
        try:
            footdev,dev = discoverPedalBoard(footboard=FOOTBOARD,wait=WAIT,oscclient=oscclient)
        except (KeyboardInterrupt, SystemExit):
            logging.info("Shutdown ...")
            return

        if footdev is None:
            logging.error('Time out get pedalboard')
            exit(-1)

        logging.info('Got %s' % footdev)
        rc = readPedalBoard(dev=dev,hostpd=PD_IP,portkey=PD_PORT_KEYS,porttap=PD_PORT_TAP,oscclient=oscclient)
        if rc == 99 :
            return
        elif rc == -2:
            logging.warning('Pedal Board not yet reachable, trying ...')
            retry -=1
            time.sleep(WAIT)
        else:
            logging.error('Exit on error')
            return

    logging.error('Abort Pedal Board not readable')
    exit(0)


if __name__ == '__main__':
    main()
