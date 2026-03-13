# PICOlightnode v2.0.18

Home Assistant Custom Integration für PICO Lighting Hardware mit MQTT-Steuerung.

---

## 📚 How To Use - Die drei Automationsebenen

Der PICO unterstützt drei verschiedene Steuerungsmodi. Du kannst zwischen ihnen wechseln je nach Bedarf.

### 🔵 **Mode 1: Manual Control (Manuelle Steuerung)**

**Wann nutzen?** Wenn du das Licht direkt im Dashboard steuern möchtest.

**Setup:**
- Keine spezielle Konfiguration nötig
- Follow External Switch: **OFF**

**Verwendung:**
```
1. Licht im Dashboard ein/ausschalten
2. Helligkeit/Farbtemperatur nach Bedarf ändern
3. Smart Restore merkt sich deine Einstellungen beim nächsten Einschalten
```

**Best for:** Ad-hoc Anpassungen, volle manuelle Kontrolle

---

### 🟢 **Mode 2: Internal Automation (PICO Daily Scheduler)**

**Wann nutzen?** Wenn der PICO seine eingebaute Automatisierung nutzen soll.

**Setup:**
1. Konfiguriere Daily Scheduler im PICO (via `setup.json`)
2. Keine HA Automations nötig
3. Follow External Switch: **OFF**

**Verwendung:**
```
1. PICO steuert sich selbst basierend auf Tageszeit
2. Funktioniert auch wenn HA offline ist
3. User kann jederzeit manuell übernehmen
4. Beim nächsten Einschalten übernimmt PICO wieder
```

**Smart Restore:**
- Ausschalten → merkt sich "device" mode
- Einschalten → PICO Daily Scheduler übernimmt wieder

**Best for:** Einfache Tageszeit-Steuerung, Standalone-Betrieb

---

### 🟡 **Mode 3: External Automation (Follow External)**

**Wann nutzen?** Wenn eine externe Automation (z.B. Keyframe Scheduler) steuern soll.

**Setup:**
1. Installiere [Keyframe Scheduler Integration](https://github.com/mjmijh/keyframe_scheduler)
2. Erstelle Keyframe Scheduler Sensor
3. Erstelle Automation mit "Keyframe Scheduler Follower" Blueprint
4. Wähle PICO Light Entity + Follow External Switch

**Verwendung:**
```
1. Schalte Follow External Switch AN
2. Keyframe Scheduler sendet kontinuierlich Werte
3. PICO folgt der externen Automation
4. User kann jederzeit manuell übernehmen → Follow disabled automatisch
```

**Smart Restore:**
- Ausschalten → merkt sich "follow" mode + brightness
- Einschalten → Startet mit gespeicherter Helligkeit
             → Keyframe übernimmt nach 1-2 Sekunden

**⚠️ Wichtig:** Follow External nur aktivieren wenn eine Automation tatsächlich läuft! Sonst bleibt das Licht beim gespeicherten Wert und reagiert nicht auf manuelle Änderungen.

**Best for:** Komplexe Zeitpläne, Sensor-basierte Anpassungen, Multi-Light Sync

---

## 🔄 Wechseln zwischen Modi

**So wechselst du den Modus:**

| Von → Nach | Wie |
|------------|-----|
| Manual → Follow External | Follow External Switch **EIN** |
| Follow External → Manual | Brightness im Dashboard ändern → Follow disabled automatisch |
| Follow External → Manual | Follow External Switch **AUS** |
| Beliebig → Internal Auto | "Alle Overrides zurücksetzen" Button klicken |

---

## 🎯 Entities Übersicht

### **Light Entity**
- `light.pico_101_{target_name}`
- Hauptsteuerung für das Licht
- Brightness + Color Temp (bei TC mode)
- **Attributes zeigen aktuellen Mode**:
  - `follow_external_automation: true/false`
  - `mode_before_off: follow/device/manual`

### **Follow External Switch**
- `switch.{target_name}_externe_automation_zulassen`
- Toggle für External Automation Mode
- Persistent über HA Neustarts

### **Button Entities**
- **Manual Override zurücksetzen**: Deaktiviert manuelle Steuerung
- **Automation Override zurücksetzen**: Deaktiviert External Automation
- **Alle Overrides zurücksetzen**: → Internal Auto Mode

---

## 📖 Vollständige Dokumentation

Für detaillierte Architektur-Informationen und das Zusammenspiel mit Keyframe Scheduler siehe:

📄 **[PICO_KEYFRAME_CONCEPT.md](docs/PICO_KEYFRAME_CONCEPT.md)**

---

## ⚙️ PICO setup.json Konfiguration

Die `setup.json` ist die zentrale Konfigurationsdatei des PICO-Geräts und legt fest, welche Lichtkanäle erzeugt werden, wie sie sich verhalten und wohin die berechneten Werte ausgegeben werden. Im Verzeichnis [`docs/examples/setup/`](docs/examples/setup/) finden sich Beispielkonfigurationen für die gängigsten DALI-Gerätetypen.

### Welches Beispiel verwenden?

| Datei | DALI-Typ | Beschreibung |
|-------|----------|--------------|
| [`dali_dt6_cct_bri.json`](docs/examples/setup/dali_dt6_cct_bri.json) | **DT6** (Standard-DALI) | CCT-Steuerung über zwei separate DAPC-Kanäle (WW + CW), plus eigenständiger BRI-Kanal |
| [`dali_dt8_cct_bri.json`](docs/examples/setup/dali_dt8_cct_bri.json) | **DT8** (Tunable White) | CCT-Steuerung nativ über ein DT8-Betriebsgerät (eine DALI-Adresse), plus eigenständiger BRI-Kanal |

**DT6** verwenden wenn: Das Betriebsgerät kein natives DT8 unterstützt. CCT wird dabei durch Mischen zweier separater DALI-Adressen realisiert – eine für Warmweiß, eine für Kaltweiß.

**DT8** verwenden wenn: Das Betriebsgerät den DALI Device Type 8 (Tunable White) vollständig implementiert. Die CCT-Steuerung erfolgt dann über einen einzelnen DALI-Befehl – präziser und synchroner als DT6.

---

### Aufbau der setup.json

Eine `setup.json` ist ein JSON-Array von **Targets**. Jeder Target repräsentiert einen Lichtkanal, der vom PICO berechnet und ausgegeben wird.

#### Target

```json
{
  "type"         : "TARGET",
  "space"        : "TC",
  "comment"      : "...",
  "behaviors"    : [...],
  "destinations" : [...]
}
```

| Feld | Bedeutung |
|------|-----------|
| `type` | Immer `"TARGET"` |
| `space` | Farbraum des Kanals: `TC` (Helligkeit + Farbtemperatur), `BRIGHTNESS` (nur Helligkeit), `RGB`, `WWCW` u.a. |
| `comment` | Freitext, empfohlen: MQTT-Pfad des Targets (z.B. `building/area/room/.../lightentityCCT`) |
| `behaviors` | Liste von Behaviors – bestimmt den Lichtwert, den der Target ausgibt |
| `destinations` | Liste von Destinations – bestimmt, wohin der berechnete Wert gesendet wird |

---

#### Behaviors

Behaviors werden in der angegebenen Reihenfolge ausgewertet. Das Ergebnis des ersten Behaviors wird an das zweite übergeben usw. In den Beispielen kommen drei Typen vor:

**STATIC** – Standardwert beim Start (Ausgangspunkt für Overrides)

```json
{
  "type"  : "STATIC",
  "point" : {
    "space"       : "TC",
    "brightness"  : 0,
    "temperature" : 2700,
    "fade"        : 0
  }
}
```

Gibt einen unveränderlichen Punkt zurück. Dient als Basis, wenn kein Override aktiv ist. `fade` gibt an, wie schnell (in Sekunden) in diesen Wert eingeblendet wird.

**OVERRIDE** – Steuerung über MQTT (Automation oder Manuell)

```json
{
  "type"           : "OVERRIDE",
  "topic"          : "building/.../lightentityCCT/override/automation",
  "defaultpoint"   : { "space": "TC", "brightness": 0, "temperature": 2700, "fade": 0 },
  "enabledatstart" : false,
  "timeout"        : -1
}
```

Abonniert ein MQTT-Topic und kann den Lichtwert bei Bedarf überschreiben. In den Beispielen gibt es immer zwei Override-Behaviors pro Target: eines für Automationen (`/override/automation`), eines für manuelle Steuerung (`/override/manual`). Diese entsprechen den HA-Entities dieser Integration.

| Feld | Bedeutung |
|------|-----------|
| `topic` | MQTT-Topic, auf das der Override reagiert |
| `defaultpoint` | Wert, der ausgegeben wird, wenn kein Point per MQTT gesendet wurde |
| `enabledatstart` | `true` = Override ist nach Reboot aktiv; `false` = inaktiv (Normalfall) |
| `timeout` | Sekunden bis zur automatischen Deaktivierung; `-1` = kein Timeout |

---

#### Destinations

Destinations bestimmen, was mit dem berechneten Lichtwert passiert.

**DALI** – Ausgabe auf den DALI-Bus

*DT8 (native CCT, eine Adresse):*

```json
{
  "type"        : "DALI",
  "conversions" : [],
  "assignments" : [
    { "type": "DT8TC", "offset": 0, "address": 0 }
  ]
}
```

`DT8TC` sendet Helligkeit und Farbtemperatur direkt an ein DALI-DT8-Betriebsgerät. Keine Konvertierung nötig.

*DT6 (CCT über zwei DAPC-Kanäle):*

```json
{
  "type"        : "DALI",
  "conversions" : [
    {
      "type"       : "TCBLEND",
      "mintemp"    : 2700,
      "minpoint"   : { "space": "WWCW", "warm": 1, "cold": 0, "fade": 0 },
      "maxtemp"    : 5700,
      "maxpoint"   : { "space": "WWCW", "warm": 0, "cold": 1, "fade": 0 },
      "blendgamma" : 1,
      "dimgamma"   : 1
    }
  ],
  "assignments" : [
    { "type": "DAPC", "offset": 0, "address": 0 },
    { "type": "DAPC", "offset": 1, "address": 1 }
  ]
}
```

`TCBLEND` konvertiert den TC-Wert (Helligkeit + Farbtemperatur) in einen WWCW-Wert (Warmweiß-Anteil + Kaltweiß-Anteil). Die beiden `DAPC`-Assignments senden Warmweiß (`offset: 0`) und Kaltweiß (`offset: 1`) als direkte Helligkeitsbefehle an zwei separate DALI-Adressen.

**HTTPSERVER** – aktuellen Zustand per HTTP abfragbar machen

```json
{ "type": "HTTPSERVER", "name": "building/.../lightentityCCT" }
```

Macht den aktuellen Lichtwert unter `http://<pico-ip>/state` abrufbar. Wird von der HA-Integration für das State-Polling genutzt.

**MESSAGING** – Zustandsänderungen per MQTT publizieren

```json
{
  "type"      : "MESSAGING",
  "topic"     : "building/.../lightentityCCT/state",
  "sendlocal" : false,
  "sendmqtt"  : true,
  "qos"       : 0,
  "retain"    : false,
  "assignments" : [
    { "trigger": "ALWAYS", "key": "brightness", "channel": "0", "asbool": false, "necessary": false },
    { "trigger": "ALWAYS", "key": "cct",        "channel": "1", "asbool": false, "necessary": false }
  ]
}
```

Publiziert den Lichtzustand auf ein MQTT-Topic. `assignments` legt fest, welche Kanäle des Farbraums in welche JSON-Keys gemappt werden. `channel: "0"` ist im TC-Raum die Helligkeit, `channel: "1"` die Farbtemperatur. Die HA-Integration abonniert dieses Topic, um den aktuellen Zustand anzuzeigen.

---

## 🎯 Was ist NEU in v2.0.18?

### ✅ Context Tracking
- Alle internen State Changes haben Context ID: `picolightnode_internal`
- Ermöglicht Blueprints zu unterscheiden zwischen User Actions und Integration Logic
- **Wichtig für Keyframe Scheduler Blueprint Manual Override Detection**

### ✅ Smart Restore verbessert
- Follow External Restore sendet gespeicherten brightness als Initialwert
- Smooth Übergang zur External Automation
- Kein "schwarzer Moment" mehr beim Einschalten

### ✅ CONF_AUTOMATION_OVERRIDE_TOPIC Fix
- Behebt Bug wo automation_override_topic nicht gefunden wurde
- Follow External funktioniert jetzt zuverlässig

---

## 🔧 Installation

```bash
cd /config
unzip -o picolightnode_v2.0.18.zip
ha core restart
```

---

## 🎯 Behavior Matrix

### Startup
```
HA startet → ALLE Overrides reset → Internal Auto
User kann Automation erstellen:
  trigger: homeassistant.start
  action: switch.turn_on (Follow External Switches)
```

### Turn-Off → Turn-On (ohne Slider)

| Vor Turn-Off | Nach Turn-On |
|--------------|--------------|
| Follow External AN | Follow External AN ✅ |
| Internal Auto | Internal Auto ✅ |
| Manual (b=64) | Manual (b=64) ✅ |

### Turn-On MIT Slider

| Vor Turn-Off | Nach Turn-On mit Slider |
|--------------|-------------------------|
| Follow External AN | Manual (Follow AUS) ✅ |
| Internal Auto | Manual ✅ |
| Manual (b=64) | Manual (b=neu) ✅ |

---

## 📊 MQTT Messages

### Startup Reset
```json
// Manual Override Topic
{"enabled": false, "point": {"space": "TC", "brightness": 1.0, "temperature": 3500, "fade": 0}}

// Automation Override Topic
{"enabled": false, "point": {"space": "TC", "brightness": 1.0, "temperature": 3500, "fade": 0}}
```

### Smart Turn-On (Follow Mode)
```json
// Automation Override Topic
{"enabled": true, "point": {"space": "TC", "brightness": 0.5, "temperature": 4000, "fade": 3.0}}
```

### Smart Turn-On (Device Mode)
```json
// Both Topics
{"enabled": false, "point": {...}}
```

---

## 🔄 Migration von v1.x

1. **Backup** alte Konfiguration
2. **Uninstall** v1.x
3. **Install** v2.0.0
4. **HA Restart**
5. **Optional**: Startup Automation erstellen für Follow External

---

## 🐛 Known Issues

**KEINE** - v2.0.0 ist ein Clean Slate! 🎯

---

## 📝 Breaking Changes

- **Alte Buttons entfernt**: "PICO interne Automatik aktivieren" → ersetzt durch "Alle Overrides zurücksetzen"
- **Startup Behavior**: Alle Overrides werden resettet (vorher: behalten)
- **State Management**: Jetzt persistent via Entity Attributes

---

**Version**: 2.0.0  
**Status**: PRODUCTION READY ✅  
**Architecture**: CLEAN & STABLE 🎯
