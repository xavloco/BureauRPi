# Bureau Raspberry Pi — plugin Domoticz

Plugin [Domoticz](https://www.domoticz.com/) pour **allumer ou couper le bureau graphique d'un Raspberry Pi** depuis Domoticz, avec arrêt automatique.

Couper le bureau libère plusieurs centaines de Mo de RAM, utile sur un RPi 3B+ (1 Go). Pratique pour n'allumer le bureau qu'au moment d'une connexion VNC (par exemple via VPN).

## Fonctionnalités

- Un **sélecteur** : `Off` | `1 h` | `2 h` | `4 h` | `Toujours allumé`
- **Arrêt automatique** après la durée choisie (durées modifiables)
- Un appareil texte qui affiche l'**heure d'arrêt prévue**
- L'état réel du bureau est relu toutes les 30 s (si le bureau est allumé ou coupé autrement, le sélecteur suit)
- L'heure d'arrêt est conservée si Domoticz redémarre
- Aucune dépendance Python à installer

## Prérequis

- Raspberry Pi OS avec bureau (`display-manager.service`)
- Domoticz avec les plugins Python activés
- L'utilisateur qui lance Domoticz doit pouvoir faire `sudo systemctl start/stop display-manager.service` sans mot de passe (c'est le cas par défaut pour l'utilisateur `pi`)

## Installation

```bash
cd ~/domoticz/plugins
git clone https://github.com/xavloco/BureauRPi.git
sudo systemctl restart domoticz
```

Mise à jour : `cd ~/domoticz/plugins/BureauRPi && git pull`, puis `sudo systemctl restart domoticz`.

Dans Domoticz : **Réglages > Matériel**, ajouter le type **« Bureau Raspberry Pi (allumer / couper) »**, régler les durées proposées (`1,2,4` par défaut), puis **Ajouter**.

Deux appareils sont créés : `Bureau RPi` (sélecteur) et `Bureau RPi arret auto` (texte).

> Les appareils ne sont créés qu'une fois. Pour changer les durées proposées, supprimer le matériel puis le recréer.

## Autorisation sudo

Si Domoticz ne tourne pas avec l'utilisateur `pi`, le journal affiche la commande exacte à lancer. Elle n'autorise que ces deux actions :

```bash
echo "UTILISATEUR ALL=(root) NOPASSWD: /usr/bin/systemctl start display-manager.service, /usr/bin/systemctl stop display-manager.service" | sudo tee /etc/sudoers.d/bureau-domoticz
sudo chmod 440 /etc/sudoers.d/bureau-domoticz
```

## Démarrer le RPi sans bureau (optionnel)

```bash
sudo systemctl set-default multi-user.target && sudo reboot
```

Pour revenir en arrière : `sudo systemctl set-default graphical.target`.

## Fonctionnement

| Sélecteur | Effet |
|---|---|
| Une durée | Le bureau démarre puis s'éteint seul à la fin |
| Toujours allumé | Le bureau reste allumé |
| Off | Le bureau s'arrête immédiatement |

## Licence

GNU GPL v3 — voir [LICENSE](LICENSE).
