#!/usr/bin/python3
# -*- coding: utf8 -*-
#####################################################################
# test clavier usb
######################################################################
import evdev
import time
import sys


def readPedalBoard(dev=None):
	try:
		for event in dev.read_loop():
			if event.type == evdev.ecodes.EV_KEY:				
				if len(dev.active_keys()) > 0:
					print('Key Code : ',dev.active_keys()[0])
								
	except (KeyboardInterrupt, SystemExit):		
		dev.close()
		return -1


allkb = {}

devices = evdev.list_devices()
for d in devices:
	dev = evdev.InputDevice(d)
	allkb[dev.name.strip()] = dev

print('Devices found %s' % allkb)


for footboard in allkb:		
	print('Read %s (Ctrl+C to stop)' % footboard)			
	rc = readPedalBoard(dev=allkb[footboard])

print('End',flush=True)
exit(0)
	


