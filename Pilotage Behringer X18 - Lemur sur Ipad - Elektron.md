#Pilotage Behringer X18, Lemur sur Ipad,Pure Data, Elektron Digitakt, Bluetooth PedalBoard.
##Jean-Yves Priou lemonasterien@gmail.com
##20201217


##Pilotage Behringer X18
Ce module permet de lire les données de la table Behringer X18
1. Tous les changements réalisés sur la table (volume, Eq ...à sont transmises à ce module via une connexion OSC.
2. Tous les changements recus de la X18 sont relayé vers l'application Lemur qui est active sur un Ipad.

La récupération des données de la X18, se fait vie un *"abonnement* déclenché via le path OSC **/xremote**

Ce module est développé en Python 3, il est nommé **readX18.py**.
Il utilise la classe OSC.py développé par  *Daniel Holth & Clinton McChesney* (https://github.com/tjoracoder/python-x32)
Cette classe à été adaptée pour Python 3

##Lemur sur Ipad
Ce module permet de lires les commandes OSC envoyés par Lemur et de les router vers la X18.
Lemur est une application Ipad qui permet de concevoir des interface utilisateur orienté Table de mixage/Surface de contrôle.

Ce module est développé en Python 3, il est nommé **sendOSCToIpad.py**.

##BlueTooth PedalBoard
Ce module permet le lire des données emisent par un pédalier BlueTooth puis de les relayer vers la Elektron Digitakt via Pure Data.

Ce module est développé en Python 3, il est nommé **readPBsendToPD.py**.

Ce module permet de calculer le TapTempo (produit par sur une touche dédiée sur le PB) et de relayer le tempo calculé à Pure Data qui le relay vers la Digitakt.
Il permet de relayer les touches **START/STOP** **PGM NETX/PREV** **MUTE ALL** **UNMUTE ALL**

* START/STOP 		Démarrage Arret de la Digitakt (touche "5")
* PGM NETX/PREV		Permet de naviguer dans les programmes de la Digitakt (touches "." / "<")
* MUTE ALL			Mute toutes les pistes (touche "0")
* UNMUTE ALL		UnMute toutes les pistes. (touche "1")
* TAP TEMPO 		Permet de modifier le tempo (touche "9")

##Pure Data
Ce module permet de piloter la BAR Elektron Digitakt.

Les modules Pure Data se nomment:
1. tap-tempo+start-stop+commande-subpatch.pd
2. counter.pd 

Ces modules permettent d'envoyer les commandes MIDI vers Elektron Digitakt.
Il reçoivent eux même les commande du module **readPBsendToPD.py** au travers d'une connexion UDP.

##Elektron Digitakt
C'est la BAR cible de cette architecture.
Les modules **BlueTooth PedalBoard** et **Pure Data** on pour but de piloter cette BAR (start,top,tempo,pgm change).

##Démarrage
Tous ces modules sont lancés en mode daemon au démarrage du RaspBerry var /etc/rc.local.
Les modules **Lemur sur Ipad** et **Pilotage Behringer X18** sont dépendants:
**Pilotage Behringer X18** ne démarre qu'après le démarrage et la connexion au réseau de **Lemur sur Ipad**.

##Architecture
TODO: Schéma



