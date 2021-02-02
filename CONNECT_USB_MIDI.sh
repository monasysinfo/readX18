#################################################################
#
# Connection automatique Keystep/Digitone,Digitakt,Korg
#
# client 20: 'Arturia KeyStep 37' [type=noyau,card=1]
#     0 'Arturia KeyStep 37 MIDI 1'
# client 24: 'Elektron Digitone' [type=noyau,card=2]
#     0 'Elektron Digitone MIDI 1'
# client 28: 'Elektron Digitakt' [type=noyau,card=3]
#     0 'Elektron Digitakt MIDI 1'
# client 32: 'minilogue xd' [type=noyau,card=4]
#     0 'minilogue xd MIDI 1'
#     1 'minilogue xd MIDI 2'
# 
# connect KeyStep 	-> 	Digitone
# 						Digitakt
# 						minilogue 0
# 						minilogue 1
# 
# aconnect 20:0 24:0
# aconnect 20:0 28:0
# aconnect 20:0 32:0 
# aconnect 20:0 32:1
# 
# 
# connect Digitakt 	->	KeyStep (pour arp et seq.)
# aconnect 28:0 20:0
#
#################################################################
KEYSTEP="Arturia KeyStep 37"
DIGITONE="Elektron Digitone"
DIGITAKT="Elektron Digitakt"
KORG="minilogue xd"

KORGID=
KEYSTEPID=
DIGITONEID=
DIGITAKTID=

KEYSTEPCNX=1
DIGITONECNX=1
DIGITAKTCNX=1
KORGCNX=1

NBTRY=10

f_getMidiId(){
	KEYSTEPID=$(aconnect -l|grep "^client.*$KEYSTEP"|awk '{print $2}')
	KORGID=$(aconnect -l|grep "^client.*$KORG"|awk '{print $2}')
	DIGITONEID=$(aconnect -l|grep "^client.*$DIGITONE"|awk '{print $2}')
	DIGITAKTID=$(aconnect -l|grep "^client.*$DIGITAKT"|awk '{print $2}')
}

f_connectMidi(){	
	aconnect ${KEYSTEPID}0 ${DIGITAKTID}0
	aconnect ${KEYSTEPID}0 ${DIGITONEID}0
	aconnect ${KEYSTEPID}0 ${KORGID}0
	aconnect ${KEYSTEPID}0 ${KORGID}1
	aconnect ${DIGITAKTID}0 ${KEYSTEPID}0
}

f_controlConnectMidi(){
	ALLCONNECT=1
	[[ $(amidi -l) = *$KEYSTEP* ]] && KEYSTEPCNX=0
	[[ $(amidi -l) = *$DIGITONE* ]] && DIGITONECNX=0
	[[ $(amidi -l) = *$DIGITAKT* ]] && DIGITAKTCNX=0
	[[ $(amidi -l) = *$KORG* ]] && KORGCNX=0
	((ALLCONNECT = KEYSTEPCNX + DIGITONECNX + DIGITAKTCNX + KORGCNX))

	printf  "$ALLCONNECT KEYSTEP : $KEYSTEPCNX\nDIGITONE : $DIGITONECNX\nDIGITAKT : $DIGITAKTCNX\nKORG : $KORGCNX\n"
}

#if [[ $ALLCONNECT = 0 ]]
#then
#	printf "OK ALLCONNECTED\n"
#else
#	printf "KO \nKEYSTEP : $KEYSTEPCNX\nDIGITONE : $DIGITONECNX\nDIGITAKT : $DIGITAKTCNX\nKORG : $KORGCNX\n"
#fi

aconnect -x

while [ $NBTRY -gt 0 ]
do
	rc=$(f_controlConnectMidi)	
	[[ $(echo $rc|awk '{print $1}') = 0 ]] && break
	printf "KO\n$rc\n"
	sleep 5
	((NBTRY-=1))
done

if [ $NBTRY -eq 0 ]
then
	printf "ABORT Connection\n"
	exit 0
fi

printf "OK \n$rc\n"
f_getMidiId
echo "KORGID=$KORGID KEYSTEPID=$KEYSTEPID DIGITONEID=$DIGITONEID DIGITAKTID=$DIGITAKTID "
f_connectMidi
