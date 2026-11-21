"""
<plugin key="BureauRPi" name="Bureau Raspberry Pi (allumer / couper)" author="Xavier" version="2.0.0">
    <description>
        <h2>Bureau Raspberry Pi</h2>
        Allume ou coupe le bureau graphique du Raspberry Pi depuis Domoticz (par exemple avant une connexion VNC).<br/>
        Un selecteur permet de choisir : Off, une duree avant arret automatique, ou Toujours allume.<br/>
        Couper le bureau libere plusieurs centaines de Mo de RAM.<br/>
        Il faut que l'utilisateur de Domoticz puisse lancer systemctl avec sudo sans mot de passe
        (c'est le cas par defaut sur Raspberry Pi OS pour l'utilisateur pi). Sinon, le journal indique la commande a lancer.
    </description>
    <params>
        <param field="Mode1" label="Durees proposees (heures, separees par des virgules)" width="120px" default="1,2,4"/>
    </params>
</plugin>
"""
# Copyright (C) 2026 Xavier
# This program is free software: you can redistribute it and/or modify it under the terms of the
# GNU General Public License as published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version. It is distributed WITHOUT ANY WARRANTY.
# See <https://www.gnu.org/licenses/>.
import Domoticz
import os
import pwd
import queue
import subprocess
import threading
import time

UNIT = "display-manager.service"
SYSTEMCTL = "/usr/bin/systemctl"
U_SWITCH, U_INFO = 1, 2


def run(cmd, timeout=25):
    """Lance une commande. Retourne (code, sortie)."""
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return r.returncode, (r.stdout + r.stderr).strip()
    except Exception as e:
        return 1, str(e)


def desktop_active():
    rc, out = run([SYSTEMCTL, "is-active", UNIT], 10)
    first = out.splitlines()[0].strip() if out else ""
    return first in ("active", "activating")


def sudoers_hint():
    try:
        user = pwd.getpwuid(os.getuid()).pw_name
    except Exception:
        user = "UTILISATEUR"
    return ('echo "%s ALL=(root) NOPASSWD: %s start %s, %s stop %s" | sudo tee /etc/sudoers.d/bureau-domoticz '
            '&& sudo chmod 440 /etc/sudoers.d/bureau-domoticz') % (user, SYSTEMCTL, UNIT, SYSTEMCTL, UNIT)


class BasePlugin:
    def __init__(self):
        self.q = queue.Queue()
        self.busy = False
        self.durations = [1, 2, 4]
        self.level = 0
        self.off_at = 0.0
        self.threads = []
        self.beat = 0
        self.active = False

    # --- cycle de vie ---
    def onStart(self):
        try:
            d = [int(x) for x in Parameters["Mode1"].replace(";", ",").split(",") if x.strip()]
            self.durations = [h for h in d if h > 0][:8] or [1, 2, 4]
        except Exception:
            self.durations = [1, 2, 4]
        if U_SWITCH not in Devices:
            names = "Off|" + "|".join("%s h" % h for h in self.durations) + "|Toujours allume"
            Domoticz.Device(Name="Bureau RPi", Unit=U_SWITCH, TypeName="Selector Switch", Switchtype=18, Used=1,
                            Options={"LevelActions": "|" * (len(self.durations) + 1), "LevelNames": names,
                                     "LevelOffHidden": "false", "SelectorStyle": "0"}).Create()
        if U_INFO not in Devices:
            Domoticz.Device(Name="Bureau RPi arret auto", Unit=U_INFO, TypeName="Text", Used=1).Create()
        try:
            cfg = Domoticz.Configuration()
            self.off_at = float(cfg.get("off_at", 0))
            self.level = int(cfg.get("level", 0))
        except Exception:
            self.off_at, self.level = 0.0, 0
        Domoticz.Heartbeat(5)           # reponse rapide apres un clic; l'etat reel est relu toutes les 30 s
        self.sync()

    def onStop(self):
        for t in self.threads:
            t.join(5)

    # --- helpers ---
    def save(self):
        try:
            Domoticz.Configuration({"off_at": self.off_at, "level": self.level})
        except Exception:
            pass

    def update(self, unit, nvalue, svalue):
        if unit in Devices and (Devices[unit].nValue != nvalue or Devices[unit].sValue != svalue):
            Devices[unit].Update(nValue=nvalue, sValue=svalue)

    def sync(self):
        """Releve l'etat reel du bureau et met a jour l'interrupteur."""
        active = desktop_active()
        self.active = active
        last = len(self.durations) + 1
        if not active and (self.off_at or self.level):
            self.off_at, self.level = 0.0, 0
            self.save()
        if active and (self.level <= 0 or self.level > last):
            self.level = last               # bureau allume autrement : on le considere permanent
            self.off_at = 0.0
            self.save()
        self.update(U_SWITCH, 1 if active else 0, str(self.level * 10))
        if active and self.off_at:
            info = "Arret a " + time.strftime("%H:%M", time.localtime(self.off_at))
        else:
            info = "Pas d'arret programme"
        self.update(U_INFO, 0, info)
        return active

    def launch(self, want, level=0, auto=False):
        if self.busy:
            Domoticz.Error("Une commande est deja en cours")
            return False
        self.busy = True

        def work():
            rc, out = run(["sudo", "-n", SYSTEMCTL, "start" if want else "stop", UNIT])
            self.q.put((want, level, auto, rc, out))
        t = threading.Thread(target=work, daemon=True)
        t.start()
        self.threads = [x for x in self.threads if x.is_alive()] + [t]
        return True

    # --- evenements Domoticz ---
    def onCommand(self, Unit, Command, Level, Color):
        if Unit != U_SWITCH:
            return
        if Command == "Off":
            level = 0
        elif Command == "On":
            level = len(self.durations) + 1
        else:
            level = max(0, min(int(Level) // 10, len(self.durations) + 1))
        if not self.launch(level > 0, level):
            self.sync()                 # remet le selecteur sur l'etat reel

    def onHeartbeat(self):
        self.beat += 1
        handled = False
        while True:
            try:
                want, level, auto, rc, out = self.q.get_nowait()
            except queue.Empty:
                break
            handled = True
            self.busy = False
            if rc == 0:
                last = len(self.durations) + 1
                self.level = level if want else 0
                self.off_at = time.time() + self.durations[level - 1] * 3600 if (want and level < last) else 0.0
                self.save()
                Domoticz.Log("Arret automatique du bureau" if auto else ("Bureau allume" if want else "Bureau coupe"))
            else:
                Domoticz.Error("Commande refusee (%s). Pour autoriser Domoticz, lance sur le RPi : %s" % (out[:120], sudoers_hint()))
        if handled or self.beat % 6 == 0:
            self.sync()
        if self.active and self.off_at and time.time() >= self.off_at and not self.busy:
            self.launch(False, 0, auto=True)


_plugin = BasePlugin()


def onStart(): _plugin.onStart()
def onStop(): _plugin.onStop()
def onHeartbeat(): _plugin.onHeartbeat()
def onCommand(Unit, Command, Level, Color): _plugin.onCommand(Unit, Command, Level, Color)
