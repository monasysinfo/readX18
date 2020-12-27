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

## Démarrage
Tous ces modules sont lancés en mode daemon au démarrage du RaspBerry var /etc/rc.local.
Les modules **Lemur/Touch OSC** et **Pilotage Behringer X18** sont dépendants:
**Pilotage Behringer X18** ne démarre qu'après le démarrage et la connexion au réseau de **Lemur/Touch OSC**.

## Architecture
TODO: Schéma




