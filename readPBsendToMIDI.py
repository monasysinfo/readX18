#!/usr/bin/python3
# -*- coding: utf8 -*-
'''
readPBsendToMIDI.py
 
This program is used to send Tap tempo, Start/Stop end Bank Change to a 
Elektron Digitakt connected with USB on the raspBerry.

21/12/2020
lemonasterien@gmail.com

'''

######################################################################
# 20201220 :    Read pedalBoard (USB/Bluetooth) and send keys to Midi Device
#               Some values are send back to Lemur on Ipad.
#
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
import configparser
import os
from threading import Timer
import mido

OSC_SEND_MSG = {'CONNECT':'/Connexion/value','TEMPO':'/Tempo/value'}
WAIT = 3
RETRY = 2400 ## Deux heures


# KEY_NAMES = {"MUTE_ALL":"0","UNMUTE_ALL":"1","START_STOP":"5","TAP_TEMPO":"9","NEXT_PGM":".","PREV_PGM":"<"}

class PedalBoardReader(object):
    '''
    Used to read the pedal board end send midi to the midi device
    '''
    defTempo = .5  # Default tempo of 120 BPM
    mintime  = 1.0   # 1 sec. is the min time betwwen 2 tap on a key (to avoid error)

    def __init__(self,dev=None,oscclient=None,midioutport=None,getbank=None,ctrl_keys=None):
        self.dev = dev        
        self.oscclient = oscclient
        self.midioutport = midioutport
        self.getbank = getbank
        self.ctrl_keys = ctrl_keys

        self.lastkey = None
        self.lktimstamp = 0  # Timestamp of the last key

    def _avoidMultipleTap(self,key):
        '''
        Return True if the tap is valid.
        A tap is valid if the previous one occurs less than self.mintime before
        '''
        if self.lastkey is None:
            self.lastkey = key
            self.lktimstamp = perf_counter()
            return True
        else:   
            if self.lastkey == key:
                curcounter = perf_counter()
                ## If delay betwwen 2 taps is less than self.mintime, we ignore this tap
                if curcounter - self.lktimstamp < self.mintime:
                    self.lktimstamp = curcounter
                    return False
                else:
                    self.lktimstamp = curcounter
                    return True
            else:
                self.lastkey == key
                return True

    def readPedalBoard(self):
        '''
        Read key pressed from the pedal board
        '''
        logging.info('Reading Pedal Board')
        tap = deque()
        elapse = None
        prevelapse = None
        mean = None    
        averagetime = self.defTempo
        puradata = False
        playing = False

        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

        try:
            for event in self.dev.read_loop():
                if event.type == evdev.ecodes.EV_KEY:
                    logging.debug('Get : %s' % evdev.categorize(event))                        
                    if event.value == 1:                        
                        if len(self.dev.active_keys()) > 0:
                            if self.dev.active_keys()[0] in self.ctrl_keys:
                                logging.debug('Get %s ' % self.ctrl_keys[self.dev.active_keys()[0]])
                                ##############################################################
                                # TAP TEMPO
                                ##############################################################
                                if self.ctrl_keys[self.dev.active_keys()[0]] == "TAP_TEMPO":
                                    if prevelapse is None:
                                        prevelapse = perf_counter()
                                    else:
                                        elapse = perf_counter()
                                        ms = elapse - prevelapse                                
                                        prevelapse = elapse
                                        if ms > 1 :     # More than 1 sec. erase tap tab
                                            tap = deque()
                                        else:
                                            tap.append(ms)

                                    if len(tap) >= 3:
                                        averagetime, bpm = self.averagetimes(tap)
                                        clockvalue = '%.4d' % int(averagetime*1000)
                                        logging.debug('Clock Value :%s, BPM : %s' % (clockvalue,int(bpm)))
                                        try:
                                            send_osc(msg="TEMPO", value=int(bpm) , oscclient=self.oscclient)
                                        except:
                                            E=traceback.format_exception(sys.exc_info()[0], sys.exc_info()[1], sys.exc_info()[2])
                                            logging.error(E)
                                        tap.popleft()

                                ##############################################################
                                # START/STOP
                                ##############################################################
                                elif self.ctrl_keys[self.dev.active_keys()[0]] == "START_STOP":                                    
                                    tap = deque()
                                    elapse = None
                                    prevelapse = None
                                    mean = None

                                    if not self._avoidMultipleTap(self.dev.active_keys()[0]):
                                        continue

                                    if not playing:
                                        playing = True                
                                        self.midioutport.send(mido.Message('start'))                    
                                        play = StartStop(averagetime/24.0,sendClock, self.midioutport) # it auto-starts, no need of rt.start()
                                    else:
                                        playing = False
                                        play.stop() # better in a try/finally block to make sure the program ends!
                                        self.midioutport.send(mido.Message('stop'))

                                ##############################################################
                                # NEXT BANK
                                ##############################################################
                                elif self.ctrl_keys[self.dev.active_keys()[0]] == "NEXT_PGM":                                    
                                    if not self._avoidMultipleTap(self.dev.active_keys()[0]):
                                        continue
                                    channel,curbank = self.getbank.curbank()
                                    curbank += 1     
                                    logging.debug('Channel : %s, Bank : %s ' % (channel,curbank))                               
                                    self.midioutport.send(mido.Message('program_change',channel=channel,program=curbank))


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

    def averagetimes(self,tap):
        '''
        Compute average time of the last 4 taps
        '''
        averagetime = sum([row for row in tap]) / float(len(tap))
        bpm = (1.0 / (averagetime / 60.0))
        return (averagetime, bpm)

class ReadMidiIn(object):
    '''
    Read current bank from Digitakt
    '''
    currentBank = (0,0)

    def __init__(self, interval, msg_type, function, *args, **kwargs):
        self._timer     = None
        self.interval   = interval
        self.function   = function
        self.args       = args
        self.kwargs     = kwargs
        self.is_running = False        
        self.msg_type   = msg_type
        self.start()

    def _run(self):        
        self.is_running = False
        self.start()
        self.function(self, self.msg_type, *self.args, **self.kwargs)

    def start(self):
        if not self.is_running:
            self._timer = Timer(self.interval, self._run)
            self._timer.start()
            self.is_running = True

    def stop(self):        
        self._timer.cancel()
        self.is_running = False

    def curbank(self):
        return self.currentBank

class StartStop(object):
    def __init__(self, interval, function, *args, **kwargs):
        self._timer     = None
        self.interval   = interval
        self.function   = function
        self.args       = args
        self.kwargs     = kwargs
        self.is_running = False
        self.bar        = 0
        self.stopreq    = False
        self.start()

    def _run(self):
        self.bar += 1
        if self.bar == 98:            
            if self.stopreq:
                self.stopreq = False
                self._timer.cancel()
                self.is_running = False
                return
            else:
                self.bar = 0
        
        self.is_running = False
        self.start()
        self.function(*self.args, **self.kwargs)

    def start(self):
        if not self.is_running:
            self._timer = Timer(self.interval, self._run)
            self._timer.start()
            self.is_running = True

    def stop(self):        
        self.stopreq = True
        while self.stopreq:
            time.sleep(.2)
        #self._timer.cancel()
        #self.is_running = False

def readBank(storeCurBank,msg_type,inport):
    midiMsg = False
    while not midiMsg:
        midiMsgData = inport.poll()
        if midiMsgData is not None:
            if midiMsgData.type == msg_type:
                storeCurBank.currentBank = (midiMsgData.channel,midiMsgData.program)
        else:
            midiMsg = True

def sendClock(outport):    
    outport.send(mido.Message('clock'))    

def send_osc(msg=None, value=None, oscclient=None):
    if oscclient is not None:
        oscclient.send_message(OSC_SEND_MSG[msg], value)

def dicoverMidiDevice(mididev=None,wait=10,retry=10,oscclient=None):
    
    send_osc(msg="CONNECT", value="Discover MIDI", oscclient=oscclient)
    logging.info('Discovering MIDI devices ...')
    midiin = None
    midiout = None
    tried = 0

    while midiin is None:
        devices = mido.get_output_names()
        for d in devices:            
            if mididev in d:
                logging.info('Device found : %s' % d)
                send_osc(msg="CONNECT", value="Found %s" % d , oscclient=oscclient)                
                midiout = d
        
        devices = mido.get_input_names()
        for d in devices:            
            if mididev in d:
                logging.info('Device found : %s' % d)
                send_osc(msg="CONNECT", value="Found %s" % d , oscclient=oscclient)                
                midiin = d
        
        if midiout is None and midiin is None:
            logging.debug('try # %s ' % tried)
            time.sleep(wait)
            tried += 1
            if tried >= retry:
                return (midiin,midiout)
            time.sleep(3)

        else:
            return(midiin,midiout)


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




def msg():
    return '''%s
        -h, help        
        -ipadadd    Adresse IP Ipad (defaut 192.168.0.5)
        -ipadport   Port OSC IPAD (defaut 8000)
        -loglevel   niveau de log [DEBUG,ERROR,WARNING,INFO]
        -config     Fichier de configuration (defaut config.ini)
        '''%sys.argv[0]

def decodeArgs():
    '''
    Decodage des arguments
    '''

    parser = argparse.ArgumentParser(description='read X18, send to Ipad', usage=msg())
    #parser.add_argument('-h', '--help', help='help',const='HELP',nargs='?')
    
    parser.add_argument('-ipadadd', help="Adresse IP Ipad (defaut 192.168.0.5)",default='192.168.0.5')
    parser.add_argument('-ipadport', help="Port OSC IPAD (defaut 8000)",default=8000)
    parser.add_argument('-loglevel', help="niveau de log [DEBUG,ERROR,WARNING,INFO]",default='INFO')
    parser.add_argument('-config', help="config file",default='config.ini')
    return parser.parse_args()

def readConfigFile(configfile=None,keys=None):
    fb = None
    midi = None    

    if os.path.isfile(configfile):
        config = configparser.ConfigParser()
        config.read(configfile)
        if 'PedalBoard' in config.sections():
            if 'bluetooth' in config['PedalBoard']:
                fb = config['PedalBoard']['bluetooth']
            elif 'usb' in config['PedalBoard']:
                fb = config['PedalBoard']['usb']

        if 'Midi' in config.sections():
            if 'digitakt' in config['Midi']:
                midi = config['Midi']['digitakt']

        if 'Buttons' in config.sections():
            if 'START_STOP' in config['Buttons']:
                keys['START_STOP'] = config['Buttons']['START_STOP']
            if 'TAP_TEMPO' in config['Buttons']:
                keys['TAP_TEMPO'] = config['Buttons']['TAP_TEMPO']
            if 'NEXT_PGM' in config['Buttons']:
                keys['NEXT_PGM'] = config['Buttons']['NEXT_PGM']

        return(True,fb,midi,keys)
    else:
        return(False,None,None,None)

def main():
    arg_analyze=decodeArgs()
    
    ipad_ip = arg_analyze.ipadadd
    ipad_osc_port = arg_analyze.ipadport    
    loglevel = arg_analyze.loglevel

    footboard = "Adafruit EZ-Key 6baa Keyboard"
    mididevice = "Elektron Digitakt"
    ctrl_keys = {82:"MUTE_ALL",79:"UNMUTE_ALL",76:"START_STOP",73:"TAP_TEMPO",83:"NEXT_PGM",86:"PREV_PGM"}

    logging.basicConfig(level=loglevel, format='%(asctime)s - %(levelname)s - readPBsendToMIDI : %(message)s', datefmt='%Y%m%d%I%M%S ')

    configfile = arg_analyze.config

    rc,fb,midi,ctrlkeys =  readConfigFile(configfile,ctrl_keys)
    if rc:
        footboard = fb
        mididevice = midi
        ctrl_keys = ctrlkeys

    
    #############################################
    # Open OSC UDP Port
    ############################################    
    oscclient = None
    try:
        oscclient = SimpleUDPClient(ipad_ip, ipad_osc_port)
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
        
    #####################################################################
    # Pedal Board Connexion
    #####################################################################
    retry = RETRY
    while retry > 0:
        try:
            ## Try to connect pedal board
            logging.info('Trying connect %s ...' % footboard)
            footdev,dev = discoverPedalBoard(footboard=footboard,wait=WAIT,oscclient=oscclient)
        except (KeyboardInterrupt, SystemExit):            
            logging.info("Shutdown ...")             
            return

        if footdev is None:
            logging.error('Time out get pedalboard')
            exit(-1)

        logging.info('Got %s' % footdev)

        #######################################################################
        # Get Pedal board, now get midi device
        #######################################################################

        midiin,midiout = dicoverMidiDevice(mididev=mididevice,wait=WAIT,oscclient=oscclient)

        midioutport   = mido.open_output(midiout)
        midiinputport = mido.open_input(midiin)
        ###########################################
        # Launch current bank reader
        ###########################################
        getbank = ReadMidiIn(.5,'program_change',readBank, midiinputport) # Read midi In

        ##########################################
        # Launch pedal board reader
        ##########################################
        pbr = PedalBoardReader(dev=dev,oscclient=oscclient,midioutport=midioutport,getbank=getbank,ctrl_keys=ctrl_keys)
        rc = pbr.readPedalBoard()
        if rc == 99 :
            getbank.stop()
            return
        elif rc == -2:
            logging.warning('Pedal Board not yet reachable, trying ...')
            retry -=1
            time.sleep(WAIT)
        else:
            getbank.stop()
            logging.error('Exit on error')
            return

    logging.error('Abort Pedal Board not readable')
    exit(0)


if __name__ == '__main__': 
    main()
