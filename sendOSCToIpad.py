#!/usr/bin/python3
# -*- coding: utf8 -*-
'''
sendOSCToIpad.py
16/12/2020
Jean-Yves Priou lemonasterien@gmail.com

Ce programme assure le relais entre LEMUR sur IPAD et la Behringer X18
L'envoie direct de commande OSC depuis LEMUR vers la X18 ne fonctionnant pas
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

SYNCHRO = '/tmp/readX18.synchro'

NBTRY = 0
TRIED = 200 # 200 * 10 seconds before stop program if LAN is not up
SLEEP = 10

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
    return parser.parse_args()

def msg():
    return '''%s
        -h, help
        -x18add     :   Adresse IP X18 (defaut 192.168.0.3)
        -x18port    :   Port OSC X18 (defaut 10024)
        -srvdadd    :   Adresse IP Serveur OSC (defaut 192.168.0.9)
        -srvport   :    Port Serveur OSC (defaut 8000)
        -loglevel   :   niveau de log [DEBUG,ERROR,WARNING,INFO] default=INFO
        '''%sys.argv[0]

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
        global TRIED
        global SYNCHRO
        global SLEEP

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
                time.sleep(SLEEP)

        if TRIED <= 0:
            logging.error("Cannot open Ipad listener %s" % E)
            return False
        else:
            logging.info('Ipad listener opened, waiting readX18 synchro ...')
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
        #TODO: Envoyer un message pour valider la connexion , le simple client UDP ne suffit pas
        global TRIED
        global SLEEP
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
                time.sleep(SLEEP)

        if TRIED <= 0:
            logging.error("cannot connect to X18 %s" % E)
            return False
        else:
            TRIED += NBTRY
            logging.info('X18 Client started')
            return True

    def default_handler(self,address, *args):
        logging.debug(f"{address}: {args}")
        value = args
        address = address
        logging.debug('send to X18 %s : %s' % (value,address))
        self.oscclientx18.send_message(address, value)

    def ch_handler(self,address, *args):
        logging.debug(f"ch_handler {address}: {args}")
        value = args
        address = address
        logging.debug('ch_handler send to X18 %s : %s' % (value,address))
        self.oscclientx18.send_message(address, value)

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
    loglevel = arg_analyze.loglevel

    logging.basicConfig(level=loglevel, format='%(asctime)s - %(levelname)s - readX18 : %(message)s', datefmt='%Y%m%d%I%M%S ')

    try:
        os.mkfifo(SYNCHRO)
    except OSError as oe:
        if oe.errno != errno.EEXIST:
            raise

    startServer(srv_address=srv_address, srv_port=srv_port, x18_address=x18_address, x18_port=x18_port)
