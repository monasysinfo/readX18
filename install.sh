#######################################################################################
# En cas de crash de la carte SD, ces commande permettent de réinstaller les services
# En pré-requis l'addresse LAN doit être fixée a 192.168.1.9
# et coté WAN : 192.168.0.1 (sur le routeur X18)
#
#######################################################################################
sudo ln -sf /usr/bin/python3.7 /usr/bin/python
mkdir -p devop/readX18
mkdir logs
echo "Copiez les fichiers dans devop/readX18, puis <enter>"
read A
cd devop/readX18
pip install -r requirements.txt
sudo cp *.service /etc/systemd/system
sudo systemctl enable connect_usb_midi.service
sudo systemctl enable sendOSCToIpad.service
sudo systemctl enable readX18.service
sudo systemctl enable readPBsendToMIDI.service

sudo systemctl start connect_usb_midi.service
sudo systemctl start sendOSCToIpad.service
sudo systemctl start readX18.service
sudo systemctl start readPBsendToMIDI.service

sudo systemctl status connect_usb_midi.service
sudo systemctl status sendOSCToIpad.service
sudo systemctl status readX18.service
sudo systemctl status readPBsendToMIDI.service

#MAJ Script de gestion bouton ON/OFF boitier argon
sudo curl https://download.argon40.com/argon1.sh | bash

sudo apt update
sudo apt full-upgrade



