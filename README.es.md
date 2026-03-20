# PICOlightnode

Integración personalizada de Home Assistant para hardware de iluminación PICO controlado mediante MQTT. El dispositivo PICO gestiona la iluminación DALI y expone sus objetivos a través de MQTT.

> Also available in [English](README.md) | Auch verfügbar auf [Deutsch](README.de.md)

---

## Requisitos

- Home Assistant 2024.1.0 o posterior
- Hardware PICO con MQTT

---

## Instalación

**Manual:**

```bash
cd /config
unzip -o picolightnode_v2.0.20.zip
ha core restart
```

**HACS (repositorio personalizado):**

Añadir `https://github.com/mjmijh/picolightnode-ha` como repositorio personalizado en HACS, instalar la integración y reiniciar Home Assistant.

---

## Modos de automatización

PICOlightnode admite tres modos de operación. Puedes cambiar entre ellos en cualquier momento.

### Modo 1: Control manual

Control directo desde el panel de Home Assistant.

- No requiere configuración especial
- Interruptor Follow External: **APAGADO**
- Smart Restore recuerda el brillo y la temperatura de color al siguiente encendido

**Ideal para:** Ajustes puntuales, control manual completo

---

### Modo 2: Automatización interna (PICO Daily Scheduler)

El dispositivo PICO se controla a sí mismo según un horario diario configurado en `setup.json`. No se necesitan automatizaciones en Home Assistant.

- Interruptor Follow External: **APAGADO**
- Funciona incluso cuando Home Assistant está desconectado
- Smart Restore: al apagar guarda el modo «device» — al encender reanuda el planificador PICO

**Ideal para:** Control basado en horarios simples, operación autónoma

---

### Modo 3: Automatización externa (Follow External)

Una automatización externa (p. ej. Keyframe Scheduler) controla la luz. PICOlightnode sigue los comandos de la automatización y detecta anulaciones manuales.

- Interruptor Follow External: **ENCENDIDO**
- Al detectar una anulación manual, el interruptor Follow External se desactiva automáticamente
- Smart Restore tras apagar desde el modo Follow: reanuda en modo manual con el brillo guardado — el modo Follow no se restaura automáticamente de forma intencionada, para evitar conflictos con la detección de anulaciones en automatizaciones externas

**Ideal para:** Horarios complejos, ajustes basados en sensores, sincronización de múltiples luces

---

### Cambio entre modos

| Desde | Hacia | Cómo |
|-------|-------|------|
| Manual | Follow External | Activar interruptor Follow External |
| Follow External | Manual | Cambiar el brillo en el panel — Follow se desactiva automáticamente |
| Follow External | Manual | Desactivar interruptor Follow External |
| Cualquiera | Automatización interna | Pulsar el botón **Restablecer todas las anulaciones** |

---

## Entidades

Por cada objetivo configurado se crean las siguientes entidades:

| Entidad | Patrón de ID | Descripción |
|---------|--------------|-------------|
| Luz | `light.<target_name>` | Entidad de luz principal — brillo y temperatura de color (modo TC) |
| Interruptor | `switch.<target_name>_externe_automation_zulassen` | Interruptor Follow External |
| Sensor | `sensor.<target_name>_dim` | Brillo actual en % (0–100) |
| Sensor | `sensor.<target_name>_cct` | Temperatura de color actual en Kelvin |
| Sensor binario | `binary_sensor.<target_name>_manual_override_active` | Anulación manual activa |
| Sensor binario | `binary_sensor.<target_name>_automation_override_active` | Anulación de automatización activa |
| Botón | — | Restablecer anulación manual |
| Botón | — | Restablecer anulación de automatización |
| Botón | — | Restablecer todas las anulaciones (vuelve al modo de automatización interna) |

### Atributos de la entidad de luz

| Atributo | Valores | Descripción |
|----------|---------|-------------|
| `follow_external_automation` | `true` / `false` | Indica si el modo Follow External está activo |
| `mode_before_off` | `follow` / `device` / `manual` | Modo que estaba activo antes de apagar la luz |

---

## Topics MQTT

| Topic | Dirección | Descripción |
|-------|-----------|-------------|
| `<base_topic>/state` | Dispositivo → HA | El dispositivo publica el estado actual (brillo, CCT) |
| `<base_topic>/override/manual` | HA → Dispositivo | La integración envía comandos de anulación manual |
| `<base_topic>/override/automation` | HA → Dispositivo | La integración envía comandos de anulación de automatización |

---

## Configuración setup.json del PICO

El archivo `setup.json` define qué canales de luz (targets) crea el PICO, cómo se comportan y a dónde se envían los valores calculados (bus DALI, MQTT, HTTP).

### Tipos de dispositivos DALI

| Tipo | Descripción |
|------|-------------|
| **DT8** | Tunable White nativo — una sola dirección DALI, CCT enviado de forma nativa mediante `DT8TC` |
| **DT6** | DALI estándar — CCT producido mezclando dos canales DAPC independientes (blanco cálido + blanco frío) |

Usar **DT8** cuando el balasto implemente completamente DALI Device Type 8. Usar **DT6** para todos los demás balastos CCT.

Las configuraciones de ejemplo para ambos tipos se encuentran en [`docs/examples/setup/`](docs/examples/setup/).

### DT8 — Vista Blockly

**Target CCT** (espacio TC, asignación DT8TC):

![DT8 CCT Target](docs/examples/setup/img/dali_dt8_cct_blockly.png)

**Target de brillo** (espacio Brightness, asignación DAPC):

![DT8 Target de brillo](docs/examples/setup/img/dali_dt8_bri_blockly.png)

### DT6 — Vista Blockly

**Target CCT** (espacio TC, conversión TCBLEND + 2× DAPC):

![DT6 CCT Target](docs/examples/setup/img/dali_dt6_cct_blockly.png)

**Target de brillo** (espacio Brightness, asignación DAPC):

![DT6 Target de brillo](docs/examples/setup/img/dali_dt6_bri_blockly.png)

### Estructura

Un archivo `setup.json` es un array JSON de **Targets**. Cada target representa un canal de luz.

```json
{
  "type"         : "TARGET",
  "space"        : "TC",
  "comment"      : "building/area/room/lightentityCCT",
  "behaviors"    : [...],
  "destinations" : [...]
}
```

**Behaviors** determinan el valor de luz. La integración utiliza dos behaviors de anulación por target — uno para control de automatización (`/override/automation`) y otro para control manual (`/override/manual`).

**Destinations** determinan a dónde se envía el valor calculado: `DALI` (salida al bus), `MESSAGING` (publicación de estado MQTT), `HTTPSERVER` (consulta de estado HTTP).

---

## Seguimiento de contexto

Todos los cambios de estado realizados internamente por la integración llevan el Context ID `picolightnode_internal`. Esto permite que blueprints externos (p. ej. Keyframe Scheduler) distingan entre acciones iniciadas por el usuario y actualizaciones internas de la integración, lo que posibilita una detección fiable de anulaciones manuales.

---

## Integraciones relacionadas

| Integración | Repositorio |
|-------------|-------------|
| Keyframe Scheduler | https://github.com/mjmijh/keyframe-scheduler |
| CCT Astronomy | https://github.com/mjmijh/cct-astronomy |

---

## Problemas y soporte

https://github.com/mjmijh/picolightnode-ha/issues
