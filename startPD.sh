#!/bin/bash
############################################################################
# Launch pure data when digitakt is connected and midi ports are availables
# lemonasterien 20111127
############################################################################

LAUNCH=0
while [ $LAUNCH -eq 0 ]
do
	MIDIPORT=$(amidi -l|grep "^IO.*Elektron Digitakt"|awk '{print $2}'|awk -F':' '{print $2}'|awk -F',' '{print $1}')
	if [[ $MIDIPORT != "" ]]
	then
		printf "LAUNCH PD MIDIPORT %s\n" $MIDIPORT
		LAUNCH=1
		/usr/bin/pd -nogui -midiindev $MIDIPORT -midioutdev $MIDIPORT -path /home/pi/Documents/Pd/externals /home/pi/devop/tap-tempo+start-stop+commande-subpatch.pd &
		#/usr/bin/pd -midiindev $MIDIPORT -midioutdev $MIDIPORT /home/pi/puredata/tap-tempo+start-stop+commande-subpatch.pd 
	else
		printf "NO DIGITAKT\n"
		sleep 5
	fi
done
exit 0
