#!/usr/bin/python3
# -*- coding: utf8 -*-
'''
This program allow the refresh of Lemur App on Ipad.

Read all OSC datas from X18  mixer then send to Lemur App on Ipad

21/12/2020
lemonasterien@gmail.com

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

SYNCHRO = '/tmp/readX18.synchro'

class BridgeX18toIpad(object):
    '''
    Relay all message from X18 to Lemur on IPAD
    '''
    status = None
    def __init__(self, ipad_address=None, ipad_port=None, x18_address=None,x18_port=None):
        super(BridgeX18toIpad, self).__init__()
        self.ipad_address = ipad_address
        self.ipad_port = ipad_port
        self.x18_address = x18_address
        self.x18_port = x18_port

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
            self.ipad_client = SimpleUDPClient(self.ipad_address, self.ipad_port)
            logging.info("connect IPAD OK")
            self.ipad_client.send_message("/Connexion/value", 'Connnect Ipad OK')
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
        self.ipad_client.send_message(addr.decode('utf8'), data)
        
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
            return

def listenX18(ipad_address=None, ipad_port=None, x18_address=None, x18_port=None):
    bx18 = BridgeX18toIpad(ipad_address=ipad_address, ipad_port=ipad_port, x18_address=x18_address, x18_port=x18_port)
    if bx18.status is None:
        bx18.get_all_x18_change_messages()
    else:
        logging.error(bx18.status)
    

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
    return parser.parse_args()

def msg():
    return '''%s
        -h, help
        -x18add     :   Adresse IP X18 (defaut 192.168.0.3)
        -x18port    :   Port OSC X18 (defaut 10024)
        -ipadadd    :   Adresse IP Ipad (defaut 192.168.0.5)
        -ipadport   :   Port OSC IPAD (defaut 8000)
        -loglevel   :   niveau de log [DEBUG,ERROR,WARNING,INFO] default=INFO
        '''%sys.argv[0]

if __name__ == '__main__':
    
    
    arg_analyze=decodeArgs()
    ipad_address = arg_analyze.ipadadd
    ipad_port = arg_analyze.ipadport
    x18_address = arg_analyze.x18add
    x18_port = arg_analyze.x18port
    loglevel = arg_analyze.loglevel

    logging.basicConfig(level=loglevel, format='%(asctime)s - %(levelname)s - readX18 : %(message)s', datefmt='%Y%m%d%I%M%S ')

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


    listenX18(ipad_address=ipad_address, ipad_port=ipad_port, x18_address=x18_address, x18_port=x18_port)
    

    