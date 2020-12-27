#!/usr/bin/python3
# -*- coding: utf8 -*-
'''
This program allow the refresh of Lemur App on Ipad.

Read all OSC datas from X18  mixer then send to Lemur App on Ipad

21/12/2020
lemonasterien@gmail.com

20201223    :   Add multi Osc clients through a config file
                If config file contains a [OSCApp] section then, all X18 messages are 
                sent to the OSC address configured in this section:
                [OSCApp]
                App One = 192.168.0.5:8000
                App Two = 192.168.0.6:9000

'''

import OSC
import time
import threading
import asyncio
import logging
from pythonosc.udp_client import SimpleUDPClient
import traceback
from pythonosc.dispatcher import Dispatcher
from pythonosc.osc_server import BlockingOSCUDPServer
from pythonosc.udp_client import SimpleUDPClient
import argparse
import sys
import os
import errno
from collections import deque
from threading import Timer
import configparser

SYNCHRO = '/tmp/readX18.synchro'
OSC_SEND_MSG = []

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

class BridgeX18toIpad(object):
    '''
    Relay all message from X18 to Lemur on IPAD
    '''
    status = None
    def __init__(self, x18_address=None,x18_port=None,oscapplist=None):
        super(BridgeX18toIpad, self).__init__()        
        self.x18_address = x18_address
        self.x18_port = x18_port
        self.hb = None
        self.oscapplist = oscapplist
        self.oscapp_client = []

        if self.connectX18():
            if not self.connectIPAD():
                self.status = 'ERROR connectIPAD'
        else:
            self.status = 'ERROR connectX18'



    def connectIPAD(self):
        '''
        Connect to IPAD
        TODO: Test if self.ipad_address is a valid  host
        '''
    
        try:
            if self.oscapplist is not None: ## Create list of ipad client link
                for ipad in self.oscapplist:
                    self.oscapp_client.append(SimpleUDPClient(self.oscapplist[ipad][0],self.oscapplist[ipad][1]))
                    logging.info("Connect IPAD %s OK" % ipad)
                
            else:
                self.oscapp_client.append(SimpleUDPClient(self.ipad_address, self.ipad_port))

                #self.oscapp_client = SimpleUDPClient(self.ipad_address, self.ipad_port)
                logging.info("Connect IPAD OK")

            send_osc("/Connexion/value",'Connnect Ipad OK',self.oscapp_client[0])

            ## HeartBeat send to first Ipad only
            self.hb = HeartBeat(.3,"/readx18/led",self.oscapp_client[0],send_osc)
            return True
            
        except:
            E=traceback.format_exception(sys.exc_info()[0], sys.exc_info()[1], sys.exc_info()[2])
            logging.error("cannot connect to IPAD %s" % E)
            return False 

    def connectX18(self):
        '''
        Connect to X18
        TODO: Test if self.x18_address is a valid  host
        '''

        self.server = OSC.OSCServer(("", self.x18_port))
        # This makes sure that client and server uses same socket. 
        # This has to be this way, as the X32 sends notifications back to same port as the /xremote message came from
        self.client = OSC.OSCClient(server=self.server) 
        tried = 20
        E = None
        while tried > 0:
            try:
                self.client.connect((self.x18_address, self.x18_port))
                break
            except:
                logging.info("TRying connect to X18...")
                E=traceback.format_exception(sys.exc_info()[0], sys.exc_info()[1], sys.exc_info()[2])
                tried -= 1
                time.sleep(10)

        if tried <= 0:
            logging.error("cannot connect to X18 %s" % E)
            return False
        else:
            logging.info("connected to X18 OK")
            return True

    def request_x18_to_send_change_notifications(self,client):
        """request_x18_to_send_change_notifications sends /xremote repeatedly to
        mixing desk to make sure changes are transmitted to our server.
        """
        t = threading.currentThread()
        
        while getattr(t, "active"):     
            try:   
                client.send(OSC.OSCMessage("/xremote"))
                time.sleep(7)
            except:
                E=traceback.format_exception(sys.exc_info()[0], sys.exc_info()[1], sys.exc_info()[2])
                logging.error(E)


    def relay_msg_to_Ipad(self,addr, tags, data, client_address):        
        
        logging.debug('%s : %s' % (addr.decode('utf8'),data))

        #send_osc(addr.decode('utf8'),data,self.oscapp_client)

        for app in self.oscapp_client:
            send_osc(addr.decode('utf8'),data,app)

        
    def get_all_x18_change_messages(self):       
       
        self.server.addMsgHandler("default", self.relay_msg_to_Ipad)

        thread = threading.Thread(target=self.request_x18_to_send_change_notifications, kwargs = {"client": self.client})
        thread.active = True
        thread.start()   
        logging.info("X18 Listener Started")

        try:
            logging.info("Starting Listener")                
            self.server.serve_forever()        
        except (KeyboardInterrupt, SystemExit):
            thread.active = False
            logging.info("Waiting for complete shutdown..")        
            thread.join()
            self.hb.stop()
            return

def send_osc(msg=None, value=None, oscclient=None):
    if oscclient is not None:
        if msg in OSC_SEND_MSG:
            oscclient.send_message(OSC_SEND_MSG[msg], value)
        else:
            oscclient.send_message(msg, value)            

def listenX18(x18_address=None, x18_port=None,oscapplist=None):
    bx18 = BridgeX18toIpad(x18_address=x18_address, x18_port=x18_port,oscapplist=oscapplist)
    if bx18.status is None:
        bx18.get_all_x18_change_messages()
    else:
        logging.error(bx18.status)
    
def readConfigFile(configfile=None,key=None):    
    oscapplist = {}
    config = configparser.ConfigParser()
    config.read(configfile)
    if key in config.sections():
        for app in config[key]:            
            oscapplist[app] = [config[key][app].split(':')[0] , int(config[key][app].split(':')[1])]
        return oscapplist
    else:
        return None

def decodeArgs():
    '''
    Decodage des arguments
    '''

    parser = argparse.ArgumentParser(description='read X18, send to Ipad', usage=msg())
    #parser.add_argument('-h', '--help', help='help',const='HELP',nargs='?')
    parser.add_argument('-x18add', help="Adresse IP X18 (defaut 192.168.0.3)", default="192.168.0.3")
    parser.add_argument('-x18port', help="Port OSC X18 (defaut 10024)",default=10024)
    parser.add_argument('-ipadadd', help="Adresse IP Ipad (defaut 192.168.0.5)",default='192.168.0.5')
    parser.add_argument('-ipadport', help="Port OSC IPAD (defaut 8000)",default=8000)
    parser.add_argument('-loglevel', help="niveau de log [DEBUG,ERROR,WARNING,INFO]",default='INFO')
    parser.add_argument('-logfile', help="log file",default='/home/pi/logs/readX18.log')
    parser.add_argument('-config', help="config file",default='config.ini')
    return parser.parse_args()

def msg():
    return '''%s
        -h, help
        -x18add     :   Adresse IP X18 (defaut 192.168.0.3)
        -x18port    :   Port OSC X18 (defaut 10024)
        -ipadadd    :   Adresse IP Ipad (defaut 192.168.0.5)
        -ipadport   :   Port OSC IPAD (defaut 8000)
        -loglevel   :   niveau de log [DEBUG,ERROR,WARNING,INFO] default=INFO
        -config     :   Fichier de configuration (defaut config.ini)
        -logfile    :   log file defaut /home/pi/logs/readX18.log
        '''%sys.argv[0]

if __name__ == '__main__':
    
    
    arg_analyze=decodeArgs()
    ipad_address = arg_analyze.ipadadd
    ipad_port = arg_analyze.ipadport
    x18_address = arg_analyze.x18add
    x18_port = arg_analyze.x18port
    loglevel = arg_analyze.loglevel
    logfile  = arg_analyze.logfile
    configfile = arg_analyze.config

    
    if logfile == 'None' :
        logging.basicConfig(level=loglevel, format='%(asctime)s - %(levelname)s - readX18 : %(message)s', datefmt='%Y%m%d%I%M%S ')
    else:
        logging.basicConfig(filename=logfile,filemode='w',level=loglevel, format='%(asctime)s - %(levelname)s - readX18 : %(message)s', datefmt='%Y%m%d%I%M%S ')


    if os.path.isfile(configfile):
        logging.info('Read config from %s' % configfile)
        oscapplist =  readConfigFile(configfile,'OSCApp')
    else:
        oscapplist = {'default':[ipad_address,ipad_port]}

    if oscapplist is None:
        logging.error('No Ipads configured in %s' % configfile)
        exit -1
    else:
        logging.info('%s' % oscapplist)

    try:
        os.mkfifo(SYNCHRO)
    except OSError as oe: 
        if oe.errno != errno.EEXIST:
            raise

    logging.info("Wait for sendOSCToIpad process ...")
    sync = None
    with open(SYNCHRO,'r') as fifo:
        logging.debug("SYNCHRO fifo opened")
        sync = fifo.read()
        fifo.close()

    logging.info('Syncho OK, start X18 listener') 


    listenX18(x18_address=x18_address, x18_port=x18_port,oscapplist=oscapplist)
    

    