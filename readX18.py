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

class BridgeX18toOSC(object):
    '''
    Relay all message from X18 to OSC client App (like Lemur on IPAD)
    '''
    status = None
    def __init__(self, x18_address=None,x18_port=None,oscapplist=None,refreshOSC=None):
        super(BridgeX18toOSC, self).__init__()
        self.x18_address = x18_address
        self.x18_port = x18_port
        self.hb = None
        self.oscapplist = oscapplist
        self.oscapp_client = []
        self.refreshOSC = refreshOSC

        if self.connectX18():
            if not self.connectOSCClient():
                self.status = 'ERROR connectOSCClient'
        else:
            self.status = 'ERROR connectX18'



    def connectOSCClient(self):
        '''
        Connect to OSC client
        '''
    
        try:
            if self.oscapplist is not None: ## Create list of ipad client link
                for osc in self.oscapplist:
                    self.oscapp_client.append(SimpleUDPClient(self.oscapplist[osc][0],self.oscapplist[osc][1]))
                    logging.info("Connect OSC client %s OK" % osc)
                
            else:
                logging.error('No OSC client configured in config.ini file')
                return False

            send_osc("/Connexion/value",'Connnect Ipad OK',self.oscapp_client[0])

            ## HeartBeat send to first Ipad only
            self.hb = HeartBeat(.3,"/readx18/led",self.oscapp_client[0],send_osc)
            return True
            
        except:
            E=traceback.format_exception(sys.exc_info()[0], sys.exc_info()[1], sys.exc_info()[2])
            logging.error("cannot connect to OSC client %s" % E)
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
                logging.info("Trying connect to X18...")
                E=traceback.format_exception(sys.exc_info()[0], sys.exc_info()[1], sys.exc_info()[2])
                tried -= 1
                time.sleep(10)

        if tried <= 0:
            logging.error("cannot connect to X18 %s" % E)
            return False
        else:
            logging.info("connected to X18 OK")
            return True

    def _refreshRequest(self,client):
        '''
        Send a refresh request for all osc path found in self.refreshOSC
        '''
        
        logging.debug(f"Refresh request {self.refreshOSC}")

        for refresh in self.refreshOSC:
            if refresh == 'buses':                
                for ch in range(1,17):
                    for bus in range(1,7):
                        oscpath = self.refreshOSC[refresh].format(channel=ch,bus=bus)                        
                        client.send(OSC.OSCMessage(oscpath))

            elif refresh == 'returnfader':
                for bus in range(1,7):
                    oscpath = self.refreshOSC[refresh].format(bus=bus)
                    client.send(OSC.OSCMessage(oscpath))

            elif refresh == 'returnmute':
                for bus in range(1,7):
                    oscpath = self.refreshOSC[refresh].format(bus=bus)
                    client.send(OSC.OSCMessage(oscpath))

            elif refresh == 'main':
                for ch in range(1,17):           
                    oscpath = self.refreshOSC[refresh].format(channel=ch)
                    client.send(OSC.OSCMessage(oscpath))

            elif refresh == 'chmute':
                for ch in range(1,17):           
                    oscpath = self.refreshOSC[refresh].format(channel=ch)
                    client.send(OSC.OSCMessage(oscpath))

            elif refresh == 'mainfader':
                oscpath = self.refreshOSC[refresh]
                client.send(OSC.OSCMessage(oscpath))

            elif refresh == 'mainmute':
                oscpath = self.refreshOSC[refresh]
                client.send(OSC.OSCMessage(oscpath))



    def request_x18_to_send_change_notifications(self,client):
        '''
        Sends /xremote repeatedly to mixing desk to make sure changes are transmitted to our server.
        '''
        t = threading.currentThread()
        
        while getattr(t, "active"):     
            try:   
                client.send(OSC.OSCMessage("/xremote"))
                self._refreshRequest(client)
                time.sleep(7)
            except:
                E=traceback.format_exception(sys.exc_info()[0], sys.exc_info()[1], sys.exc_info()[2])
                logging.error(E)


    def relay_msg_to_OSC_client(self,addr, tags, data, client_address):        
        
        logging.debug('%s : %s' % (addr.decode('utf8'),data))

        #send_osc(addr.decode('utf8'),data,self.oscapp_client)

        for app in self.oscapp_client:
            send_osc(addr.decode('utf8'),data,app)

        
    def get_all_x18_change_messages(self):
        '''
        Listen all OSC messages from the X18 Mixer
        '''
       
        self.server.addMsgHandler("default", self.relay_msg_to_OSC_client)        

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

def listenX18(x18_address=None, x18_port=None,oscapplist=None,refreshOSC=None):
    bx18 = BridgeX18toOSC(x18_address=x18_address, x18_port=x18_port,oscapplist=oscapplist,refreshOSC=refreshOSC)
    if bx18.status is None:
        bx18.get_all_x18_change_messages()
    else:
        logging.error(bx18.status)
    
def readConfigFile(configfile=None,section=None,key=None):    
    conflist = {}
    config = configparser.ConfigParser()
    config.read(configfile)
    if section in config.sections():
        if key is None:
            for app in config[section]:            
                conflist[app] = [config[section][app].split(':')[0] , int(config[section][app].split(':')[1])]
            return conflist
        elif key in config[section] :
            return config[section][key]
        else:
            return None
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
    parser.add_argument('-oscadd', help="Adresse IP OSC client (defaut 192.168.0.5)",default='192.168.0.5')
    parser.add_argument('-oscport', help="Port OSC client (defaut 8000)",default=8000)
    parser.add_argument('-loglevel', help="niveau de log [DEBUG,ERROR,WARNING,INFO]",default='INFO')
    parser.add_argument('-logfile', help="log file",default='/home/pi/logs/readX18.log')
    parser.add_argument('-config', help="config file",default='config.ini')
    return parser.parse_args()

def msg():
    return '''%s
        -h, help
        -x18add     :   Adresse IP X18 (defaut 192.168.0.3)
        -x18port    :   Port OSC X18 (defaut 10024)
        -oscadd    :   Adresse IP Ipad (defaut 192.168.0.5)
        -oscport   :   Port OSC IPAD (defaut 8000)
        -loglevel   :   niveau de log [DEBUG,ERROR,WARNING,INFO] default=INFO
        -config     :   Fichier de configuration (defaut config.ini)
        -logfile    :   log file defaut /home/pi/logs/readX18.log
        '''%sys.argv[0]

if __name__ == '__main__':
    
    
    arg_analyze=decodeArgs()
    osc_client_address = arg_analyze.oscadd
    osc_port = arg_analyze.oscport
    x18_address = arg_analyze.x18add
    x18_port = arg_analyze.x18port
    loglevel = arg_analyze.loglevel
    logfile  = arg_analyze.logfile
    configfile = arg_analyze.config

    refreshOSC = {'buses':None, 'main':None, 'returnfader':None, 'returnmute':None, 'mainfader':None, 'mainmute':None, 'chmute':None}

    if logfile == 'None' :
        logging.basicConfig(level=loglevel, format='%(asctime)s - %(levelname)s - readX18 : %(message)s', datefmt='%Y%m%d%I%M%S ')
    else:
        logging.basicConfig(filename=logfile,filemode='w',level=loglevel, format='%(asctime)s - %(levelname)s - readX18 : %(message)s', datefmt='%Y%m%d%I%M%S ')


    if os.path.isfile(configfile):
        logging.info('Read config from %s' % configfile)
        oscapplist =  readConfigFile(configfile,section='OSCApp')
        x18_address = readConfigFile(configfile,section='X18',key='ip')
        x18_port = readConfigFile(configfile,section='X18',key='port')
        if x18_port is None:
            x18_port = 10024
        else:
            x18_port = int(x18_port)

        for k in refreshOSC:
            refreshOSC[k] = readConfigFile(configfile,section='Refresh',key=k)
        logging.info('Refresh OSC path : %s' % refreshOSC)
    else:
        oscapplist = {'default':[osc_client_address,osc_port]}

    if oscapplist is None:
        logging.error('No OSC client configured in %s' % configfile)
        exit(-1)
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


    listenX18(x18_address=x18_address, x18_port=x18_port,oscapplist=oscapplist,refreshOSC=refreshOSC)
    

    