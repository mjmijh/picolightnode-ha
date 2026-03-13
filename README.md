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
