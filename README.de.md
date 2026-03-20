# PICOlightnode v2.0.19

Home-Assistant-Custom-Integration fur PICO-Beleuchtungshardware mit MQTT-Steuerung. Das PICO-Gerat verwaltet DALI-Beleuchtung und stellt seine Targets uber MQTT bereit.

- [README (English)](README.md)
- [README (Espanol)](README.es.md)

---

## Voraussetzungen

- Home Assistant 2024.1.0 oder neuer
- PICO-Hardware mit MQTT

---

## Installation

**Manuell:**

```bash
cd /config
unzip -o picolightnode_v2.0.19.zip
ha core restart
```

**HACS (Custom Repository):**

`https://github.com/mjmijh/picolightnode-ha` als Custom Repository in HACS hinzufugen, die Integration installieren und Home Assistant neu starten.

---

## Automationsmodi

PICOlightnode unterstutzt drei Betriebsmodi. Du kannst jederzeit zwischen ihnen wechseln.

### Modus 1: Manuelle Steuerung

Direkte Steuerung uber das Home-Assistant-Dashboard.

- Keine spezielle Konfiguration notwendig
- Follow-External-Schalter: **AUS**
- Smart Restore merkt sich Helligkeit und Farbtemperatur beim nachsten Einschalten

**Geeignet fur:** Spontane Anpassungen, vollstandige manuelle Kontrolle

---

### Modus 2: Interne Automation (PICO Daily Scheduler)

Das PICO-Gerat steuert sich selbst anhand eines in `setup.json` konfigurierten Tageszeit-Plans. Keine HA-Automationen notwendig.

- Follow-External-Schalter: **AUS**
- Funktioniert auch wenn Home Assistant offline ist
- Smart Restore: Ausschalten speichert den Modus "device" — Einschalten startet den PICO-Scheduler wieder

**Geeignet fur:** Einfache zeitbasierte Steuerung, Standalone-Betrieb

---

### Modus 3: Externe Automation (Follow External)

Eine externe Automation (z. B. Keyframe Scheduler) steuert das Licht. PICOlightnode verfolgt Befehle der Automation und erkennt manuelle Eingriffe.

- Follow-External-Schalter: **EIN**
- Bei erkanntem manuellen Eingriff wird der Follow-External-Schalter automatisch deaktiviert
- Smart Restore nach Ausschalten aus dem Follow-Modus: Neustart im manuellen Modus mit gespeicherter Helligkeit — Follow wird absichtlich nicht automatisch wiederhergestellt, um Konflikte mit der Override-Erkennung externer Automationen zu vermeiden

**Geeignet fur:** Komplexe Zeitplane, sensorbasierte Anpassungen, Multi-Licht-Synchronisation

---

### Wechseln zwischen Modi

| Von | Nach | Vorgehensweise |
|-----|------|----------------|
| Manuell | Follow External | Follow-External-Schalter **EIN** |
| Follow External | Manuell | Helligkeit im Dashboard andern — Follow deaktiviert sich automatisch |
| Follow External | Manuell | Follow-External-Schalter **AUS** |
| Beliebig | Interne Automation | Schaltflache **Alle Overrides zurucksetzen** drucken |

---

## Entities

Fur jedes konfigurierte Target werden folgende Entities erstellt:

| Entity | ID-Muster | Beschreibung |
|--------|-----------|--------------|
| Licht | `light.<target_name>` | Haupt-Light-Entity — Helligkeit und Farbtemperatur (TC-Modus) |
| Schalter | `switch.<target_name>_externe_automation_zulassen` | Follow-External-Schalter |
| Schaltflache | — | Manuellen Override zurucksetzen |
| Schaltflache | — | Automation-Override zurucksetzen |
| Schaltflache | — | Alle Overrides zurucksetzen (kehrt zur internen Automation zuruck) |

### Attribute der Light-Entity

| Attribut | Werte | Beschreibung |
|-----------|-------|--------------|
| `follow_external_automation` | `true` / `false` | Gibt an, ob der Follow-External-Modus aktiv ist |
| `mode_before_off` | `follow` / `device` / `manual` | Modus, der vor dem Ausschalten aktiv war |

---

## MQTT-Topics

| Topic | Richtung | Beschreibung |
|-------|----------|--------------|
| `<base_topic>/state` | Gerat → HA | Gerat publiziert den aktuellen Zustand (Helligkeit, CCT) |
| `<base_topic>/override/manual` | HA → Gerat | Integration sendet manuelle Override-Befehle |
| `<base_topic>/override/automation` | HA → Gerat | Integration sendet Automation-Override-Befehle |

---

## PICO-Konfiguration setup.json

Die Datei `setup.json` legt fest, welche Lichtkanale (Targets) der PICO erzeugt, wie sie sich verhalten und wohin die berechneten Werte gesendet werden (DALI-Bus, MQTT, HTTP).

### DALI-Geratetypen

| Typ | Beschreibung |
|-----|--------------|
| **DT8** | Natives Tunable White — einzelne DALI-Adresse, CCT wird nativ uber `DT8TC` gesendet |
| **DT6** | Standard-DALI — CCT durch Mischung zweier separater DAPC-Kanale (Warmweiss + Kaltweiss) |

**DT8** verwenden, wenn das Betriebsgerat DALI Device Type 8 vollstandig implementiert. Fur alle anderen CCT-Betriebsgerate **DT6** verwenden.

Beispielkonfigurationen fur beide Typen befinden sich in [`docs/examples/setup/`](docs/examples/setup/).

### Aufbau

Eine `setup.json` ist ein JSON-Array von **Targets**. Jeder Target reprasentiert einen Lichtkanal.

```json
{
  "type"         : "TARGET",
  "space"        : "TC",
  "comment"      : "building/area/room/lightentityCCT",
  "behaviors"    : [...],
  "destinations" : [...]
}
```

**Behaviors** bestimmen den Lichtwert. Die Integration verwendet pro Target zwei Override-Behaviors — eines fur Automationssteuerung (`/override/automation`) und eines fur manuelle Steuerung (`/override/manual`).

**Destinations** legen fest, wohin der berechnete Wert gesendet wird: `DALI` (Bus-Ausgabe), `MESSAGING` (MQTT-Statuspublikation), `HTTPSERVER` (HTTP-Statusabfrage).

---

## Context Tracking

Alle internen Zustandsanderungen der Integration tragen die Context-ID `picolightnode_internal`. Dadurch konnen externe Blueprints (z. B. Keyframe Scheduler) zwischen Benutzeraktionen und integrationsinternen Aktualisierungen unterscheiden — Grundlage fur eine zuverlassige manuelle Override-Erkennung.

---

## Verwandte Integrationen

| Integration | Repository |
|-------------|------------|
| Keyframe Scheduler | https://github.com/mjmijh/keyframe-scheduler |
| CCT Astronomy | https://github.com/mjmijh/cct-astronomy |

---

## Probleme und Support

https://github.com/mjmijh/picolightnode-ha/issues
