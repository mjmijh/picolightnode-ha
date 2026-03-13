# PICOlightnode + Keyframe Scheduler - Konzept & Architektur

## Übersicht

Dieses Dokument beschreibt das Zusammenspiel zwischen der **PICOlightnode Integration**, dem **Keyframe Scheduler** und den **Blueprints**.

---

## 1. Die drei Automationsebenen des PICO

Der PICO unterstützt drei verschiedene Arten der Lichtsteuerung:

### 🔵 **Level 1: Manual Override (Manuelle Steuerung)**

**Beschreibung**: User steuert das Licht direkt über das Dashboard oder per Service Call.

**MQTT Topic**: `{target}/override/manual`

**Payload Example**:
```json
{
  "enabled": true,
  "point": {
    "brightness": 0.5,
    "temperature": 3500,
    "fade": 2.0
  }
}
```

**Verhalten**:
- Höchste Priorität - überschreibt alles andere
- User hat volle Kontrolle
- Follow External Switch: **OFF**

**Use Cases**:
- User schaltet Licht im Dashboard ein/aus
- User ändert Helligkeit/Farbtemperatur manuell
- Schnelle Ad-hoc Anpassungen

---

### 🟢 **Level 2: Internal Automation (PICO-interne Automatik)**

**Beschreibung**: Der PICO hat eine eingebaute Automatisierung (z.B. Daily Scheduler im PICO Firmware).

**MQTT**: Keine MQTT-Steuerung nötig - läuft komplett im PICO

**Verhalten**:
- PICO steuert sich selbst basierend auf interner Logik
- Unabhängig von Home Assistant
- Funktioniert auch wenn HA offline ist
- Follow External Switch: **OFF**

**Use Cases**:
- PICO mit eingebautem Daily Scheduler
- Einfache Tageszeit-basierte Steuerung
- Standalone-Betrieb ohne externe Systeme

**Smart Restore Verhalten**:
```
User schaltet Licht AUS → mode_before_off = "device"
User schaltet Licht EIN → PICO übernimmt wieder mit interner Automatik
```

---

### 🟡 **Level 3: External Automation (Follow External)**

**Beschreibung**: Eine externe Automation (z.B. Keyframe Scheduler) steuert den PICO über MQTT.

**MQTT Topic**: `{target}/override/automation`

**Payload Example**:
```json
{
  "enabled": true,
  "point": {
    "brightness": 0.75,
    "temperature": 2700,
    "fade": 3.0
  }
}
```

**Verhalten**:
- Externe Automation sendet kontinuierlich Werte
- PICO folgt den externen Vorgaben
- Follow External Switch: **ON**

**Use Cases**:
- Keyframe Scheduler mit komplexen Zeitplänen
- Adaptive Lighting basierend auf Sensoren
- Synchronisation mehrerer Lichter
- Content Engines (z.B. Ambilight-Effekte)

**Smart Restore Verhalten**:
```
User schaltet Licht AUS → mode_before_off = "follow"
User schaltet Licht EIN → External Automation übernimmt wieder
                        → Initial brightness = gespeicherter Wert
                        → Dann External Automation sendet neue Werte
```

---

## 2. PICOlightnode Integration

### **Kernfunktion**
Stellt PICO Hardware als Home Assistant Light Entities dar und managed die MQTT-Kommunikation.

### **Wichtige Entities**

#### **Light Entity**
- Hauptentity für Lichtsteuerung
- Unterstützt brightness und color_temp (bei TC mode)
- **Smart Restore**: Merkt sich den Mode vor dem Ausschalten

#### **Follow External Switch**
- Toggle zwischen Manual und External Automation
- Steuert `automation_override` MQTT Topic
- Persistent über Neustarts

#### **Button Entities**
- **Manual Override Reset**: Deaktiviert Manual Override
- **Automation Override Reset**: Deaktiviert External Automation
- **All Overrides Reset**: Deaktiviert beide → PICO internal automation

### **Context Tracking**
Die Integration setzt bei internen State Changes einen speziellen Context:

```python
context=Context(id="picolightnode_internal")
```

**Angewendet bei**:
- Smart Restore nach Einschalten
- MQTT State Updates vom PICO
- Button Entity Actions

**NICHT angewendet bei**:
- User Clicks im Dashboard (verwendet HA default context)

**Zweck**: Ermöglicht Blueprints zu unterscheiden zwischen:
- ✅ Echter User-Interaktion (Manual Override)
- ❌ Interner Integration-Logik (kein Manual Override)

---

## 3. Keyframe Scheduler Integration

### **Kernfunktion**
Interpoliert Keyframe-Werte (brightness, color temperature) über Zeit und stellt sie als Sensor bereit.

### **Output Sensor**
```yaml
sensor.my_keyframe_cct:
  state: 127  # brightness (0-255)
  attributes:
    brightness_01: 0.5        # brightness (0.0-1.0)
    temperature_k: 3500       # Kelvin
    transition_seconds: 2.5   # Empfohlene Transition
```

### **Was Keyframe Scheduler NICHT macht**
- ❌ Sendet NICHT direkt an Lichter
- ❌ Weiß nichts über PICO Hardware
- ❌ Nur **Data Provider** - Blueprints/Automations wenden die Werte an

### **Kompatibilität**
Funktioniert mit **ALLEN** Light-Typen:
- Philips Hue
- WLED
- **PICOlightnode** ✅
- Zigbee Lights
- DMX Fixtures
- Standard HA Lights

---

## 4. Keyframe Scheduler Follower Blueprint

### **Location**
`keyframe_scheduler/blueprints/automation/keyframe_smart_light_follower.yaml`

### **Funktion**
Wendet Keyframe Scheduler Werte auf ein Light Entity an mit intelligenter Manual Override Detection.

### **Features**

#### **A) Keyframe Application**
- Liest Werte vom Keyframe Scheduler Sensor
- Sendet an Light Entity (für PICO: via automation override MQTT)
- Unterstützt smooth transitions

#### **B) Manual Override Detection**
Erkennt wenn User das Licht manuell steuert und disabled dann automatisch "Follow External".

**Detection Logic**:
```yaml
{% set has_user = trigger.to_state.context.user_id is not none %}
{% set has_parent = trigger.to_state.context.parent_id is not none %}
{% set context_id = trigger.to_state.context.id | default('') %}
{% set from_pico = 'picolightnode' in context_id %}

# Manual Override = User Action, NOT from automation, NOT from PICO internal
{{ has_user and not from_automation and not from_pico }}
```

**Context Sources**:

| Quelle | user_id | parent_id | context.id | Manual Override? |
|--------|---------|-----------|------------|------------------|
| User klickt Dashboard | ✅ | ❌ | (default) | **✅ YES** |
| User ändert brightness | ✅ | ❌ | (default) | **✅ YES** |
| Keyframe Blueprint | ❌ | ✅ | (auto) | ❌ NO |
| PICO Smart Restore | ❌ | ❌ | picolightnode_internal | ❌ NO |
| PICO MQTT Update | ❌ | ❌ | picolightnode_internal | ❌ NO |
| Andere Automation | ❌ | ✅ | (auto) | ❌ NO |

#### **C) Smooth Sync on Enable**
Wenn Follow External aktiviert wird, synct das Licht smooth zum aktuellen Keyframe-Wert (3s transition).

---

## 5. Typische Workflows

### **Workflow 1: External Automation (Keyframe Scheduler)**

```
Setup:
1. Erstelle Keyframe Scheduler Sensor (sensor.office_lighting)
2. Erstelle Automation mit "Keyframe Scheduler Follower" Blueprint
3. Wähle PICO Light Entity
4. Wähle Follow External Switch

Betrieb:
- Keyframe Scheduler läuft und sendet kontinuierlich Werte
- Blueprint wendet Werte an via automation override MQTT
- Follow External Switch ist ON
- User kann jederzeit manuell übernehmen → Follow disabled automatisch

Smart Restore:
- User schaltet aus → mode_before_off = "follow"
- User schaltet ein → Restored mit saved brightness
                     → Keyframe übernimmt nach 1-2 Sekunden
```

---

### **Workflow 2: Internal Automation (PICO Daily Scheduler)**

```
Setup:
1. Konfiguriere Daily Scheduler im PICO (via setup.json)
2. Keine Follow External Switch nötig
3. Keine Blueprints/Automations nötig

Betrieb:
- PICO steuert sich selbst basierend auf Tageszeit
- Komplett unabhängig von Home Assistant
- Follow External Switch ist OFF

Smart Restore:
- User schaltet aus → mode_before_off = "device"
- User schaltet ein → PICO Daily Scheduler übernimmt wieder
```

---

### **Workflow 3: Manual Only**

```
Setup:
- Keine Automations
- Keine Follow External

Betrieb:
- User steuert komplett manuell über Dashboard
- Follow External Switch ist OFF

Smart Restore:
- User schaltet aus → mode_before_off = "manual"
- User schaltet ein → Restored mit saved brightness
```

---

## 6. Priority & Override Hierarchy

```
┌─────────────────────────────────────┐
│   Manual Override (enabled: true)   │  ← Höchste Priorität
│   User hat direkte Kontrolle        │
└─────────────────────────────────────┘
              ↓ disabled
┌─────────────────────────────────────┐
│ Automation Override (enabled: true) │  ← Mittlere Priorität
│ External Automation steuert         │
└─────────────────────────────────────┘
              ↓ disabled
┌─────────────────────────────────────┐
│   PICO Internal Automation          │  ← Niedrigste Priorität
│   (z.B. Daily Scheduler)            │
└─────────────────────────────────────┘
```

**Beispiel Szenarien**:

```
Scenario A: User Override während External Automation
- Keyframe Scheduler läuft (automation override enabled)
- User ändert brightness im Dashboard
→ Manual override enabled
→ Keyframe Blueprint detect Manual Override
→ Follow External Switch → OFF
→ User hat jetzt Kontrolle

Scenario B: Alle Overrides disabled
- User klickt "All Overrides Reset" Button
→ manual override disabled
→ automation override disabled
→ PICO internal automation übernimmt
```

---

## 7. Best Practices

### **Wann welchen Mode nutzen?**

**Manual Mode** - Für:
- ✅ Ad-hoc Lichtsteuerung
- ✅ Schnelle Anpassungen
- ✅ Wenn keine Automation benötigt

**Internal Automation** - Für:
- ✅ Einfache Tageszeit-basierte Steuerung
- ✅ Standalone-Betrieb (HA kann offline sein)
- ✅ Wenn PICO Firmware Scheduler ausreicht

**External Automation (Follow External)** - Für:
- ✅ Komplexe Zeitpläne mit vielen Keyframes
- ✅ Sensor-basierte Anpassungen (Bewegung, Helligkeit)
- ✅ Synchronisation mehrerer Lichter
- ✅ Integration mit anderen HA-Systemen

---

### **Follow External - Wichtiger Hinweis**

⚠️ **Wenn "Follow External" aktiviert ist, aber KEINE externe Automation läuft:**

Das Licht wird mit der zuletzt gespeicherten Helligkeit eingeschaltet und bleibt dort. Es reagiert NICHT auf manuelle Änderungen im Dashboard solange Follow External AN ist.

**Lösung**: Follow External Switch manuell ausschalten.

**Best Practice**: Follow External nur aktivieren wenn eine externe Automation (z.B. Keyframe Scheduler) tatsächlich läuft!

---

## 8. Troubleshooting

### **Problem: Follow External Switch geht nicht auf ON nach Einschalten**

**Ursache**: Eine Automation (z.B. Keyframe Blueprint) detected fälschlicherweise Manual Override.

**Check**: 
- Ist v2.0.18+ der PICOlightnode Integration installiert?
- Ist v3.0.10+ des Keyframe Scheduler Blueprints installiert?

**Diese Versionen haben Context Tracking für korrekte Manual Override Detection.**

---

### **Problem: Licht reagiert nicht auf Keyframe Scheduler**

**Check**:
1. Ist Follow External Switch ON?
2. Läuft die Keyframe Follower Automation?
3. Hat die Automation die richtige Light Entity ausgewählt?
4. Sendet der Keyframe Scheduler Sensor Werte? (Dev Tools → States)

---

### **Problem: Nach HA Neustart ist Mode verloren**

**Check**:
- PICOlightnode v2.0.x nutzt `RestoreEntity` - Mode sollte persistent sein
- Logs checken: "Restored mode_before_off=..."
- Follow External Switch State wird über HA Neustarts gespeichert

---

## 9. Versionen & Kompatibilität

### **Minimum Requirements**

| Component | Minimum Version | Feature |
|-----------|----------------|---------|
| PICOlightnode | v2.0.18 | Context Tracking |
| Keyframe Scheduler | v3.0.9 | Basic Follower Blueprint |
| Keyframe Scheduler | v3.0.10 | PICO Context Detection |

### **Backwards Compatibility**

Nicht erforderlich - alle Komponenten werden zusammen verwendet und geupdated.

---

## 10. Zukünftige Entwicklungen

### **PICO Firmware Updates**

Wenn der PICO in Zukunft MQTT State-Feedback für Overrides sendet:

```json
{
  "manual_override": { "enabled": true },
  "automation_override": { "enabled": false }
}
```

Dann kann die Integration `follow_external` auch basierend auf MQTT synchronisieren.

**Aktuell**: `follow_external` ist ein rein HA-seitiges Setting (User Preference).

---

## Zusammenfassung

Die Kombination aus **PICOlightnode Integration** + **Keyframe Scheduler** + **Follower Blueprint** bietet:

✅ **Drei Automationsebenen**: Manual, Internal, External  
✅ **Smart Restore**: Mode wird über Aus/Ein-Zyklen behalten  
✅ **Intelligente Manual Override Detection**: Unterscheidet User vs. Automation  
✅ **Context Tracking**: Blueprints können PICO-interne Actions ignorieren  
✅ **Universelle Kompatibilität**: Keyframe Scheduler funktioniert mit allen Lights  
✅ **Flexible Workflows**: Von einfach (Manual) bis komplex (Multi-Keyframe)  

---

**Version**: 2024-03-13  
**Autoren**: PICOlightnode Integration + Keyframe Scheduler Integration
