#!/usr/bin/python3
# -*- coding: utf8 -*-
'''
readPBsendToMIDI.py
 
This program is used to send Tap tempo, Start/Stop end Bank Change to a 
Elektron Digitakt connected with USB on the raspBerry.

21/12/2020
lemonasterien@gmail.com



######################################################################
20201220 :  Read pedalBoard (USB/Bluetooth) and send keys to Midi Device
            Some values are send back to Lemur on Ipad.

20201224 :  Add the multi reader pedal board.

######################################################################
'''
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
import threading
import mido

OSC_SEND_MSG = {'CONNECT':'/Connexion/value','TEMPO':'/Tempo/value'}
WAIT = 3
RETRY = 2400 ## Deux heures


# KEY_NAMES = {"MUTE_ALL":"0","UNMUTE_ALL":"1","START_STOP":"5","TAP_TEMPO":"9","NEXT_PGM":".","PREV_PGM":"<"}

class PedalBoardReader(object):
    '''
    Used to read the pedal board end send midi to the midi device
    '''
    defTempo = .5       # Default tempo of 120 BPM
    mintime  = 1.0      # 1 sec. is the min time betwwen 2 tap on a key (to avoid error)
    playing = False     # Current state
    otherReaders = None # List of all readers to transmit current state (playing/stop)
    stopNow  = False    # If True, stop the reader
    play     = None     # link to the StartStop object

    def __init__(self,dev=None,oscclient=None,midioutport=None,getbank=None,ctrl_keys=None):
        self.dev = dev        
        self.oscclient = oscclient
        self.midioutport = midioutport
        self.getbank = getbank
        self.ctrl_keys = ctrl_keys

        self.lastkey = None
        self.lktimstamp = 0  # Timestamp of the last key
        self.averagetime = self.defTempo
        self.bpm = None


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

    def eventReader(self,sock):
        '''
        Read Keyboards events
        '''
        tap = deque()
        elapse = None
        prevelapse = None
        mean = None        
        puradata = False

        for event in self.dev.read_loop():
            if self.stopNow :
                logging.info('Stop request receive')
                exit(99)

            if event.type == evdev.ecodes.EV_KEY:                    
                if event.value == 1:             
                    logging.debug('Get : %s' % evdev.categorize(event))
                    
                    channel,curbank = self.getbank.curbank()
                    logging.debug('Channel : %s, Bank : %s ' % (channel,curbank))
                    
                    if len(self.dev.active_keys()) > 0:
                        if self.dev.active_keys()[0] in self.ctrl_keys:
                            logging.debug('Get %s ' % self.ctrl_keys[self.dev.active_keys()[0]])                                
                            ##############################################################
                            # TAP TEMPO
                            ##############################################################
                            ## 20210108 drop non registered key
                            if len(self.dev.active_keys()) == 0:
                                continue
                            if not self.dev.active_keys()[0] in self.ctrl_keys:
                                continue

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
                                    self.averagetime, self.bpm = self.averagetimes(tap)
                                    # send current tempo to other readers instances
                                    for other in self.otherReaders:
                                        other.averagetime = self.averagetime
                                        other.bpm = self.bpm

                                    clockvalue = '%.4d' % int(self.averagetime*1000)
                                    logging.debug('Clock Value :%s, BPM : %s' % (clockvalue,int(self.bpm)))
                                    try:
                                        send_osc(msg="TEMPO", value=int(self.bpm) , oscclient=self.oscclient)
                                    except:                                        
                                        E=traceback.format_exception(sys.exc_info()[0], sys.exc_info()[1], sys.exc_info()[2])
                                        logging.error('04 - %s' % E)
                                        send_osc(msg="/errormess", value=E , oscclient=self.oscclient)
                                    tap.popleft()

                            ##############################################################
                            # START/STOP
                            ##############################################################
                            elif self.ctrl_keys[self.dev.active_keys()[0]] == "START_STOP":                                    
                                tap = deque()
                                elapse = None
                                prevelapse = None
                                mean = None

                                logging.debug('%s' % mido.get_output_names())

                                if not self._avoidMultipleTap(self.dev.active_keys()[0]):
                                    continue

                                logging.debug('self.playing %s' % self.playing)
                                if not self.playing:
                                    logging.debug('Send START')
                                    self.midioutport.send(mido.Message('start'))                                        
                                    self.play = StartStop(self.averagetime/24.0, self.midioutport) # it auto-starts, no need of rt.start()
                                    # send current state to other readers instances
                                    for other in self.otherReaders:
                                        other.playing = True
                                        other.play = self.play
                                else:
                                    for other in self.otherReaders:
                                        other.playing = False
                                    
                                    self.play.stop() # better in a try/finally block to make sure the program ends!
                                    logging.debug('Send STOP')
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

                            ## 250210109 Add Reset button for emergency situations
                            elif self.ctrl_keys[self.dev.active_keys()[0]] == "RESET":
                                send_osc(msg="/errormess", value='RESET' , oscclient=self.oscclient)
                                logging.info('Reset service')
                                for other in self.otherReaders:
                                    other.stopNow = True
                                exit(99)

    def readPedalBoard(self):
        '''
        Read key pressed from the pedal board
        '''        
        logging.info('Reading Pedal Board')
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

        try:
            self.eventReader(sock)
                                
        except (KeyboardInterrupt, SystemExit):            
                logging.info("2 - Shutdown from readPedalBoard ...")             
                return 99
        except (OSError) as err:
            logging.error('05 - %s' % err)
            send_osc(msg="/errormess", value=err , oscclient=self.oscclient)
            return -2
        except:        
            E=traceback.format_exception(sys.exc_info()[0], sys.exc_info()[1], sys.exc_info()[2])
            logging.error('06 - %s' % E)
            send_osc(msg="/errormess", value=E , oscclient=self.oscclient)
            sock.close()
            return -1

    def averagetimes(self,tap):
        '''
        Compute average time of the last 4 taps
        '''
        averagetime = sum([row for row in tap]) / float(len(tap))
        bpm = (1.0 / (averagetime / 60.0))
        return (averagetime, bpm)


class HeartBeat(object):
    '''
    Send HeartBeat to Lemur App
    '''

    def __init__(self, interval, msg_type, oscclient,sendfunction):
        self._timer     = None
        self.interval   = interval
        self.oscclient   = oscclient    
        self.sendfunction = sendfunction     
        self.is_running = False        
        self.msg_type   = msg_type

        self.led = deque()
        self.led.append(1)
        self.led.append(0)
        self.led.append(0)
        self.led.append(0)

        self.start()

    def _sendLed(self):
        for i in range(0,len(self.led)):    
            self.sendfunction(msg='%s%s' % (self.msg_type,str(i)), value=self.led[i], oscclient=self.oscclient)
        self.led.rotate(1)

    def _run(self):        
        self.is_running = False
        self.start()
        self._sendLed()

    def start(self):
        if not self.is_running:
            self._timer = Timer(self.interval, self._run)
            self._timer.start()
            self.is_running = True

    def stop(self):        
        self._timer.cancel()
        self.is_running = False


class ReadMidiIn(object):
    '''
    Read current bank from Digitakt
    '''
    currentBank = (0,0)

    def __init__(self, interval, msg_type, inport):
        self._timer     = None
        self.interval   = interval        
        self.inport     = inport        
        self.is_running = False        
        self.msg_type   = msg_type
        self.start()

    def _readBank(self):
        midiMsg = False
        while not midiMsg:
            midiMsgData = self.inport.poll()
            if midiMsgData is not None:
                if midiMsgData.type == self.msg_type:
                    self.currentBank = (midiMsgData.channel,midiMsgData.program)
            else:
                midiMsg = True

    def _run(self):        
        self.is_running = False
        self.start()
        self._readBank()

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
    def __init__(self, interval, outport):
        self._timer     = None
        self.interval   = interval        
        self.outport    = outport        
        self.is_running = False
        self.bar        = 0
        self.stopreq    = False
        self.start()

    def _sendClock(self):    
        self.outport.send(mido.Message('clock'))   

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
        self._sendClock()

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

def send_osc(msg=None, value=None, oscclient=None):
    if oscclient is not None:
        if msg in OSC_SEND_MSG:
            oscclient.send_message(OSC_SEND_MSG[msg], value)
        else:
            oscclient.send_message(msg, value)

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
                logging.info('Output midi device found : %s' % d)
                send_osc(msg="CONNECT", value="Found %s" % d , oscclient=oscclient)                
                midiout = d
        
        devices = mido.get_input_names()
        for d in devices:            
            if mididev in d:
                logging.info('Input midi device found : %s' % d)
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


def discoverPedalBoard(footboard=None,wait=10,retry=10,oscclient=None,usedFootdev=None):
    
    send_osc(msg="CONNECT", value="Discover BT", oscclient=oscclient)
    logging.info('Searching Pedal Board %s ...' % footboard)
    footdev = None
    dev = None
    tried = 0

    while footdev is None:
        devices = evdev.list_devices()
        for d in devices:            
            if d in usedFootdev:
                tried += 1
                if tried >= retry:
                    return (None,None) 
                continue
            dev = evdev.InputDevice(d)
            if dev.name.strip() == footboard.strip():
                logging.info('Device found : %s' % footboard)
                send_osc(msg="CONNECT", value="Found %s" % footboard , oscclient=oscclient)                
                footdev = d
                return (footdev,dev)
            else:
                logging.debug('try # %s ' % tried)
                time.sleep(wait)
                tried += 1
                if tried >= retry:
                    return (None,None) 
        time.sleep(3)




def msg():
    return '''%s
        -h, help        
        -ipadadd    Adresse IP Ipad (defaut 192.168.0.5)
        -ipadport   Port OSC IPAD (defaut 8000)
        -loglevel   niveau de log [DEBUG,ERROR,WARNING,INFO]
        -config     Fichier de configuration (defaut config.ini)
        -logfile	log file defaut /home/pi/logs/readPBsendToMIDI.log

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
    parser.add_argument('-logfile', help="log file",default='/home/pi/logs/readPBsendToMIDI.log')

    return parser.parse_args()

def readConfigFile(configfile=None):
    fb = []
    midi = None
    keyconfig = {}
    
    if os.path.isfile(configfile):
        config = configparser.ConfigParser()
        config.read(configfile)
        if 'PedalBoard' in config.sections():
            if 'pbs' in config['PedalBoard']:
                fb = fb + config['PedalBoard']['pbs'].split(',')
                #fb.append(config['PedalBoard']['pbs'])
            

        if 'Midi' in config.sections():
            if 'digitakt' in config['Midi']:
                midi = config['Midi']['digitakt']

        for b in fb:
            keys = {}
            if b in config.sections():
                if 'START_STOP' in config[b]:
                    keys[int(config[b]['START_STOP'])] = 'START_STOP'
                if 'TAP_TEMPO' in config[b]:
                    keys[int(config[b]['TAP_TEMPO'])] = 'TAP_TEMPO'
                if 'NEXT_PGM' in config[b]:
                    keys[int(config[b]['NEXT_PGM'])] = 'NEXT_PGM'
                ## 20210109 Add reset button
                if 'RESET' in config[b]:
                    keys[int(config[b]['RESET'])] = 'RESET'
                keyconfig[b] = keys

            elif 'Buttons' in config.sections():
                if 'START_STOP' in config['Buttons']:
                    keys[int(config['Buttons']['START_STOP'])] = 'START_STOP'
                if 'TAP_TEMPO' in config['Buttons']:
                    keys[int(config['Buttons']['TAP_TEMPO'])] = 'TAP_TEMPO'
                if 'NEXT_PGM' in config['Buttons']:
                    keys[int(config['Buttons']['NEXT_PGM'])] = 'NEXT_PGM'
                ## 20210109 Add reset button
                if 'RESET' in config['Buttons']:
                    keys[int(config['Buttons']['RESET'])] = 'RESET'
                keyconfig[b] = keys

        return(True,fb,midi,keyconfig)
    else:
        return(False,None,None,None)

def main():
    arg_analyze=decodeArgs()
    
    ipad_ip = arg_analyze.ipadadd
    ipad_osc_port = arg_analyze.ipadport    
    loglevel = arg_analyze.loglevel
    logfile  = arg_analyze.logfile

    footboards = None
    mididevice = None
    #ctrl_keys = {82:"MUTE_ALL",79:"UNMUTE_ALL",76:"START_STOP",73:"TAP_TEMPO",83:"NEXT_PGM",86:"PREV_PGM"}

    if logfile == 'None' :
        logging.basicConfig(level=loglevel, format='%(asctime)s - %(levelname)s - readPBsendToMIDI : %(message)s', datefmt='%Y%m%d%I%M%S ')
    else:
        logging.basicConfig(filename=logfile,filemode='w',level=loglevel, format='%(asctime)s - %(levelname)s - readPBsendToMIDI : %(message)s', datefmt='%Y%m%d%I%M%S ')

    configfile = arg_analyze.config

    rc,footboards,mididevice,keyconfig =  readConfigFile(configfile)

    if not rc:
        logging.error('07 - No suitable config found in %s' % configfile)
        exit(-1)

    
    #############################################
    # Open OSC UDP Port
    ############################################    
    oscclient = None
    try:
        oscclient = SimpleUDPClient(ipad_ip, ipad_osc_port)
    except:
        E=traceback.format_exception(sys.exc_info()[0], sys.exc_info()[1], sys.exc_info()[2])
        logging.error('01 - %s' % E)

    ######################################################
    # Attempt to send OSC to OSC App to validate connexion
    ######################################################
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
        logging.error("02- cannot connect to IPAD %s" % E)
        exit(-1)
    else:
        logging.info('Connected to IPAD')
        
    #####################################################################
    # Pedals Boards Connexion
    #####################################################################
    allpb = {}
    usedFootdev = []
    for pb in footboards:
        retry = 5
        while retry > 0:
            try:
                ## Try to connect pedal board
                logging.info('Trying connect %s ...' % pb)
                footdev,dev = discoverPedalBoard(footboard=pb,wait=WAIT,retry=retry,oscclient=oscclient,usedFootdev=usedFootdev)
                if dev is not None:                    
                    allpb[footdev] = [dev,pb]
                    usedFootdev.append(footdev)

            except (KeyboardInterrupt, SystemExit):            
                logging.info("3 - Shutdown ...")             
                return

            if footdev is None:
                logging.error('03 - Time out get pedalboard')                

            logging.info('Got %s' % footdev)
            break

    #######################################################################
    # Get Pedal board, now get midi device
    #######################################################################

    midiin,midiout = dicoverMidiDevice(mididev=mididevice,wait=WAIT,retry=retry,oscclient=oscclient)

    if midiin is None and midiout is None:
    	logging.erroe('No midi device available')
    	exit( -1)

    midioutport   = mido.open_output(midiout)
    midiinputport = mido.open_input(midiin)
    ###########################################
    # Launch current bank reader
    ###########################################
    getbank = ReadMidiIn(.5,'program_change', midiinputport) # Read midi In

    ##########################################
    # Launch HeartBeat
    ##########################################
    hb = HeartBeat(.3,"/readpb/led",oscclient,send_osc)

    ##########################################
    # Launch pedal board reader
    ##########################################
    readers = []
    for pb in allpb:
        logging.debug('KEYS %s' % keyconfig[allpb[pb][1]])
        readers.append(PedalBoardReader(dev=allpb[pb][0],oscclient=oscclient,midioutport=midioutport,getbank=getbank,ctrl_keys=keyconfig[allpb[pb][1]]))

    readthreads = []

    for reader in readers:
        reader.otherReaders = readers

        readthreads.append(threading.Thread(target=reader.readPedalBoard))

    for readthread in readthreads:
        readthread.start()

    try:
        while True:
            ## If readthreads is 0 length, then we shutdown.
            ## This occurs if a reset has been requested
            if len(readthreads) == 0:
                getbank.stop()
                hb.stop()
                logging.info('Exit code 9')
                return 9

            for i,readthread in enumerate(readthreads):
                if not readthread.is_alive():
                    readthreads.pop(i)
                #logging.debug("Is alive %s" % readthread.is_alive())
            time.sleep(1)

    except (KeyboardInterrupt, SystemExit):
        for reader in readers:
            reader.stopNow = True        
        
        logging.info("1 - Tap a key to shutdown ...")

        nbt = len(readthreads)
        while True:
            for readthread in readthreads:                
                if readthread.is_alive():                    
                    time.sleep(1)
                else:
                    nbt -= 1
                    if nbt == 0:
                        break
            break
        getbank.stop()
        hb.stop()
        return 0

    # if rc == 99 :
    #     getbank.stop()
    #     hb.stop()
    #     return
    # elif rc == -2:
    #     logging.warning('Pedal Board not yet reachable, trying ...')
    #     retry -=1
    #     time.sleep(WAIT)
    # else:
    #     getbank.stop()
    #     hb.stop()
    #     logging.error('Exit on error')
    #     return
# 
    # logging.error('Abort Pedal Board not readable')
    # exit(0)


if __name__ == '__main__': 
    cr = main()
    exit(cr)

