#!/usr/bin/python3
# -*- coding: utf8 -*-
'''
Ce programme assure le relais entre LEMUR sur IPAD et la Behringer X18
L'envoie direct de commande OSC depuis LEMUR vers la X18 ne fonctionnant pas, ce program recois les données
de Lemur puis les relais vars la X18

21/12/2020
lemonasterien@gmail.com

'''

from pythonosc.dispatcher import Dispatcher
from pythonosc.osc_server import BlockingOSCUDPServer
from pythonosc.udp_client import SimpleUDPClient
import argparse
import sys
import logging
import traceback
import time
import os
import errno
from collections import deque
from threading import Timer

SYNCHRO = '/tmp/readX18.synchro'

NBTRY = 0
TRIED = 200 # 200 * 10 seconds before stop program if LAN is not up
OSC_SEND_MSG = []
WAIT = 3
RETRY = 2400 ## Deux heures

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

class X18ToIpadRelay():
    status = None
    def __init__(self, srv_address=None, srv_port=None, x18_address=None, x18_port=None):
        super(X18ToIpadRelay, self).__init__()
        self.srv_address = srv_address
        self.srv_port = srv_port
        self.x18_address = x18_address
        self.x18_port = x18_port        
        self.dispatcher = Dispatcher()
        self.dispatcher.map("/ch/*", self.ch_handler)
        self.dispatcher.set_default_handler(self.default_handler)
        if self.connectX18():
            self.startListener()
        else:
            self.status = "ERROR connectX18"

    def startListener(self):
        '''
        Start a listener for le Lemur datas (from Ipad)
        Theses datas are then transfert to X18 Mixer
        '''
        global TRIED
        global SYNCHRO
        global WAIT

        E = None
        while TRIED > 0:
            logging.info('Trying open Ipad listener %s' % TRIED)
            try:
                self.server = BlockingOSCUDPServer((self.srv_address, self.srv_port), self.dispatcher)
                logging.info('Ipad listener started')
                break
               
            except:
                E=traceback.format_exception(sys.exc_info()[0], sys.exc_info()[1], sys.exc_info()[2])
                logging.info('Re-try opening Ipad listener ... %s' % TRIED)                    
                TRIED -= 1
                time.sleep(WAIT)

        if TRIED <= 0:
            logging.error("Cannot open Ipad listener %s" % E)
            return False
        else:
            logging.info('Ipad listener opened, waiting readX18 synchro ...')
            #######################################################################
            # Synchronisation with readX18 process
            #######################################################################
            with open(SYNCHRO,'w') as fifo:
                logging.debug("SYNCHRO fifo opened")
                fifo.write('sync')
                fifo.close()

            logging.info('Synchro OK, starting server ...')    

            try:
                self.server.serve_forever()  # Blocks forever          
            except (KeyboardInterrupt, SystemExit):        
                logging.info("Shutdown server..")        
                return

    def connectX18(self):
        '''
        Connect to the X18 mixer
        '''
        #TODO: Envoyer un message pour valider la connexion , le simple client UDP ne suffit pas
        global TRIED        
        global WAIT
        global NBTRY

        E = None
        while TRIED > 0:
            try:
                logging.info('Trying connect X18... %s' % TRIED)
                self.oscclientx18 = SimpleUDPClient(self.x18_address, self.x18_port)
                self.oscclientx18.send_message('/nop', '')
                break    
            except:
                logging.info('Re-trying connect X18... %s' % TRIED)
                E=traceback.format_exception(sys.exc_info()[0], sys.exc_info()[1], sys.exc_info()[2])
                TRIED -= 1
                NBTRY += 1
                time.sleep(WAIT)

        if TRIED <= 0:
            logging.error("cannot connect to X18 %s" % E)
            return False
        else:
            TRIED += NBTRY
            logging.info('X18 Client started')
            return True

    def default_handler(self,address, *args):
        '''
        Default OSC messages from Lemeur handler
        '''
        logging.debug(f"{address}: {args}")
        value = args
        address = address
        logging.debug('send to X18 %s : %s' % (value,address))
        self.oscclientx18.send_message(address, value)

    def ch_handler(self,address, *args):
        '''
        /ch OAS messages from Lemur handler
        '''
        logging.debug(f"ch_handler {address}: {args}")
        value = args
        address = address
        logging.debug('ch_handler send to X18 %s : %s' % (value,address))
        self.oscclientx18.send_message(address, value)

def send_osc(msg=None, value=None, oscclient=None):
    if oscclient is not None:
        if msg in OSC_SEND_MSG:
            oscclient.send_message(OSC_SEND_MSG[msg], value)
        else:
            oscclient.send_message(msg, value)            

def decodeArgs():
    '''
    Decodage des arguments
    '''

    parser = argparse.ArgumentParser(description='read X18, send to Ipad', usage=msg())
    #parser.add_argument('-h', '--help', help='help',const='HELP',nargs='?')
    parser.add_argument('-x18add', help="Adresse IP X18 (defaut 192.168.0.3)", default="192.168.0.3")
    parser.add_argument('-x18port', help="Port OSC X18 (defaut 10024)",default=10024)
    parser.add_argument('-srvadd', help="Adresse IP Serveur OSC (defaut 192.168.0.9)",default='192.168.0.9')
    parser.add_argument('-srvport', help="Port Serveur OSC (defaut 8000)",default=8000)
    parser.add_argument('-loglevel', help="niveau de log [DEBUG,ERROR,WARNING,INFO]",default='INFO')
    parser.add_argument('-ipadadd', help="Adresse IP Ipad (defaut 192.168.0.5)",default='192.168.0.5')
    parser.add_argument('-ipadport', help="Port OSC IPAD (defaut 8000)",default=8000)
    parser.add_argument('-logfile', help="log file",default='/home/pi/logs/sendOSCToIpad.log')
    return parser.parse_args()

def msg():
    return '''%s
        -h, help
        -x18add     :   Adresse IP X18 (defaut 192.168.0.3)
        -x18port    :   Port OSC X18 (defaut 10024)
        -srvdadd    :   Adresse IP Serveur OSC (defaut 192.168.0.9)
        -srvport   :    Port Serveur OSC (defaut 8000)
        -loglevel   :   niveau de log [DEBUG,ERROR,WARNING,INFO] default=INFO
        -ipadadd    :   Adresse IP Ipad defaut 192.168.0.5
        -ipadport   :   Port OSC IPAD defaut 8000)
        -logfile    :   log file defaut /home/pi/logs/sendOSCToIpad.log
        '''%sys.argv[0]

def startServer(srv_address=None, srv_port=None, x18_address=None, x18_port=None):
    relay = X18ToIpadRelay(srv_address=srv_address, srv_port=srv_port, x18_address=x18_address, x18_port=x18_port) 
    if relay.status is not None:
        logging.error(relay.status)

if __name__ == '__main__':
    
    arg_analyze=decodeArgs()
    srv_address = arg_analyze.srvadd
    srv_port = arg_analyze.srvport
    x18_address = arg_analyze.x18add
    x18_port = arg_analyze.x18port
    ipad_address = arg_analyze.ipadadd
    ipad_port = arg_analyze.ipadport

    loglevel = arg_analyze.loglevel
    logfile  = arg_analyze.logfile

    
    logging.basicConfig(filename=logfile,filemode='a',level=loglevel, format='%(asctime)s - %(levelname)s - sendOSCToIpad : %(message)s', datefmt='%Y%m%d%I%M%S ')

    ## Create Named Pipe, if not exists, for synchronisation with readX18.py
    try:
        os.mkfifo(SYNCHRO)
    except OSError as oe: 
        if oe.errno != errno.EEXIST:
            raise

    #############################################
    # Open OSC UDP Port to lemur on Ipad
    ############################################    
    oscclient = None
    try:
        oscclient = SimpleUDPClient(ipad_address, ipad_port)
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

    hb = HeartBeat(.3,"/osclemur/led",oscclient,send_osc)
    startServer(srv_address=srv_address, srv_port=srv_port, x18_address=x18_address, x18_port=x18_port)
    hb.stop()
    
