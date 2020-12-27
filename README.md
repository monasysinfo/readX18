# RaspBerry tools for controling pedal Board, Behringer X18 mix table, Lemur/ Touch OSC app (on Ipad/Android)
## Jean-Yves Priou lemonasterien@gmail.com
## 17/12/2020


## Pilotage Behringer X18
Ce module permet de lire les données de la table Behringer X18
1. Tous les changements réalisés sur la table (volume, Eq ...à sont transmises à ce module via une connexion OSC.
2. Tous les changements recus de la X18 sont relayés vers les applications de type Lemur/Touch OSC configurées dans le fichier config.ini.

La récupération des données de la X18, se fait via un *"abonnement* déclenché via le path OSC **/xremote**

Ce module est développé en Python 3, il est nommé **readX18.py**.
Il utilise la classe OSC.py développé par  *Daniel Holth & Clinton McChesney* (https://github.com/tjoracoder/python-x32)
Cette classe à été adaptée pour Python 3

## Lemur/Touch OSC (IPad/Android)
Ces applications permettent de lire/envoyer des commandes OSC vers un hôte défini dans l'application.

Le programme python3 **sendOSCToIpad.py** permet de lire les commandes OSC par ces applications puis de les relayer vers la X18.

## Lecture de Pedal Board
Ce module permet le lire des données emisent par un ou plusieurs pédalier (BlueTooth,USB) puis de transformer les informations
revues en messages MIDI qui seront relayés vers un (seul) périphérique midi (Boîte à rythm, SYnthé ...)

Le cas d'utilisation est de pouvoir piloter un Elektron Digitak à partir de plusieurs télécommandes.

Ce module est développé en Python 3, il est nommé **readPBsendToMIDI.py**.

Ce module permet de calculer le TapTempo (produit par sur une touche dédiée sur le PB) et de relayer le tempo calculé à une horloge qui sera envoyée au 
disposifif midi cible.

Il permet de relayer les touches **START/STOP** **PGM NETX**

* START/STOP 		Démarrage Arret d'une sequence.
* PGM NETX  		Passe au programme suivant
* TAP TEMPO 		Permet de piloter le tempo de l'horloge

## Elektron Digitakt
C'est la BAR cible de cette architecture.

## Modules d'installation et de démarrage sur RaspBerry

Tous les fichiers de ce projet doivent être copiés dans le répertoire $HOME/devop/readX18 du raspberry (créer le répertoire manuellement).
Les fichiers journaux sont écrits dans le répertoire $HOME/logs (créez le répertoire manuellement)

Installez toutes les bibliothèques python:

```shell
pip install -r ~ / devop / readX18 / requirements.txt
```

La configuration personnalisée peut être effectuée en éditant le fichier **\*.service** et le fichier **config.ini**.

Pour déterminer le nom du clavie USB/Bluetooth, utilisez la bibliothèque evdev python:

```python
importer evdev
impression (evdev.list_devices ())
```

Tous les modules sont lancés en mode démon lors du démarrage du RaspBerry via 3 services:
* readPBsendToMIDI.service
* readX18.service
* sendOSCToIpad.service

Ces fichiers de services doivent être copiés dans le répertoire /lib/systemd/system.
Ensuite, utilisez cette commande pour activer, démarrer les services:

```shell
sudo systemctl activer readPBsendToMIDI
sudo systemctl activer readX18
sudo systemctl activer sendOSCToIpad
sudo start readPBsendToMIDI
sudo start readX18
sudo start sendOSCToIpad
```

Les modules **Lemur/Touch OSC** et **Pilotage Behringer X18** sont dépendants:
**Pilotage Behringer X18** ne démarre qu'après le démarrage et la connexion au réseau de **Lemur/Touch OSC**.

## Architecture
TODO: Schéma

# English Version
# RaspBerry tools for controling pedal Board, Behringer X18 mix table, Lemur / Touch OSC app (on Ipad / Android)
## Jean-Yves Priou lemonasterien@gmail.com
## 12/17/2020


## Behringer X18 control
This module allows you to read data from the Behringer X18 mixer
1. All changes made to the table (volume, Eq ... to are transmitted to this module via an OSC connection.
2. All changes received from the X18 are relayed to the Lemur / Touch OSC type applications configured in the config.ini file.

Data recovery from the X18 is done via a *subscription* triggered via the OSC **/xremote** path

This module is developed in Python 3, it is named **readX18.py**.
It uses the OSC.py class developed by *Daniel Holth & Clinton McChesney* (https://github.com/tjoracoder/python-x32)
This class has been adapted for Python 3

## Lemur / Touch OSC (IPad / Android)
These applications allow to read / send OSC commands to a host defined in the application.

The python3 **sendOSCToIpad.py** program is used to read OSC commands by these applications and then relay them to the X18.

## Play Pedal Board
This module allows the reading of data emitted by one or more pedals (BlueTooth, USB) then transforming the information
reviews in MIDI messages which will be relayed to a (single) midi device (Drum machine, Synth ...)

The use case is to be able to control an **Elektron Digitak** from several remote controls.

This module is developed in Python 3, it is named **readPBsendToMIDI.py**.

This module allow to calculate the TapTempo (produced by a dedicated key on the PB) and to relay the calculated tempo to a clock that will be sent to the
target midi device.

It is also used to relay the **START/STOP** **PGM NETX** keys

* START / STOP Start Stop of a sequence.
* PGM NETX Goes to the next program
* TAP TEMPO Allows you to control the clock tempo

## Elektron Digitakt
This is the target BAR of this architecture.

## Installation and Start-up modules on RaspBerry

All the files of this project have to be copied in the $HOME/devop/readX18 of the raspberry (create dir manually).
Logs file are writen in $HOME/logs directory (create dir manually)

Install all python libraries:

```shell
pip install -r ~/devop/readX18/requirements.txt
```

Custom configuration can be done by editing **\*.service** file and the **config.ini** file.

To determine the name of the US/Bluetooth keyboard, use the evdev python library:

```python
import evdev
print(evdev.list_devices())
```

All modules are launched in daemon mode when starting the RaspBerry through 3 services : 
* readPBsendToMIDI.service
* readX18.service
* sendOSCToIpad.service

These services files have to be copy in the /lib/systemd/system directory.
Then use this command to enable, start and stop services:

```shell
sudo systemctl enable readPBsendToMIDI
sudo systemctl enable readX18
sudo systemctl enable sendOSCToIpad
sudo start readPBsendToMIDI
sudo start readX18
sudo start sendOSCToIpad
```

The **Lemur/Touch OSC** and **Behringer X18 Control** modules are dependents.
**Behringer X18 control** does not start until after **Lemur / Touch OSC** has started up and connected to the network.

## Architecture
TODO: Diagram

