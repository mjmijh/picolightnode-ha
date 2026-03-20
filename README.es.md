# PICOlightnode v2.0.19

Integracion personalizada de Home Assistant para hardware de iluminacion PICO controlado mediante MQTT. El dispositivo PICO gestiona la iluminacion DALI y expone sus objetivos a traves de MQTT.

- [README (English)](README.md)
- [README (Deutsch)](README.de.md)

---

## Requisitos

- Home Assistant 2024.1.0 o posterior
- Hardware PICO con MQTT

---

## Instalacion

**Manual:**

```bash
cd /config
unzip -o picolightnode_v2.0.19.zip
ha core restart
```

**HACS (repositorio personalizado):**

Agregar `https://github.com/mjmijh/picolightnode-ha` como repositorio personalizado en HACS, instalar la integracion y reiniciar Home Assistant.

---

## Modos de automatizacion

PICOlightnode admite tres modos de operacion. Puedes cambiar entre ellos en cualquier momento.

### Modo 1: Control manual

Control directo desde el panel de Home Assistant.

- No requiere configuracion especial
- Interruptor Follow External: **APAGADO**
- Smart Restore recuerda el brillo y la temperatura de color al siguiente encendido

**Ideal para:** Ajustes puntuales, control manual completo

---

### Modo 2: Automatizacion interna (PICO Daily Scheduler)

El dispositivo PICO se controla a si mismo segun un horario diario configurado en `setup.json`. No se necesitan automatizaciones en Home Assistant.

- Interruptor Follow External: **APAGADO**
- Funciona incluso cuando Home Assistant esta desconectado
- Smart Restore: al apagar guarda el modo "device" — al encender reanuda el planificador PICO

**Ideal para:** Control basado en horarios simples, operacion autonoma

---

### Modo 3: Automatizacion externa (Follow External)

Una automatizacion externa (p. ej. Keyframe Scheduler) controla la luz. PICOlightnode sigue los comandos de la automatizacion y detecta anulaciones manuales.

- Interruptor Follow External: **ENCENDIDO**
- Al detectar una anulacion manual, el interruptor Follow External se desactiva automaticamente
- Smart Restore tras apagar desde el modo Follow: reanuda en modo manual con el brillo guardado — el modo Follow no se restaura automaticamente de forma intencionada, para evitar conflictos con la deteccion de anulaciones en automatizaciones externas

**Ideal para:** Horarios complejos, ajustes basados en sensores, sincronizacion de multiples luces

---

### Cambio entre modos

| Desde | Hacia | Como |
|-------|-------|------|
| Manual | Follow External | Activar interruptor Follow External |
| Follow External | Manual | Cambiar el brillo en el panel — Follow se desactiva automaticamente |
| Follow External | Manual | Desactivar interruptor Follow External |
| Cualquiera | Automatizacion interna | Pulsar el boton **Restablecer todas las anulaciones** |

---

## Entidades

Por cada objetivo configurado se crean las siguientes entidades:

| Entidad | Patron de ID | Descripcion |
|---------|--------------|-------------|
| Luz | `light.<target_name>` | Entidad de luz principal — brillo y temperatura de color (modo TC) |
| Interruptor | `switch.<target_name>_externe_automation_zulassen` | Interruptor Follow External |
| Boton | — | Restablecer anulacion manual |
| Boton | — | Restablecer anulacion de automatizacion |
| Boton | — | Restablecer todas las anulaciones (vuelve al modo de automatizacion interna) |

### Atributos de la entidad de luz

| Atributo | Valores | Descripcion |
|----------|---------|-------------|
| `follow_external_automation` | `true` / `false` | Indica si el modo Follow External esta activo |
| `mode_before_off` | `follow` / `device` / `manual` | Modo que estaba activo antes de apagar la luz |

---

## Topics MQTT

| Topic | Direccion | Descripcion |
|-------|-----------|-------------|
| `<base_topic>/state` | Dispositivo → HA | El dispositivo publica el estado actual (brillo, cct) |
| `<base_topic>/override/manual` | HA → Dispositivo | La integracion envia comandos de anulacion manual |
| `<base_topic>/override/automation` | HA → Dispositivo | La integracion envia comandos de anulacion de automatizacion |

---

## Configuracion setup.json del PICO

El archivo `setup.json` define que canales de luz (targets) crea el PICO, como se comportan y a donde se envian los valores calculados (bus DALI, MQTT, HTTP).

### Tipos de dispositivos DALI

| Tipo | Descripcion |
|------|-------------|
| **DT8** | Tunable White nativo — una sola direccion DALI, CCT enviado de forma nativa mediante `DT8TC` |
| **DT6** | DALI estandar — CCT producido mezclando dos canales DAPC independientes (blanco calido + blanco frio) |

Usar **DT8** cuando el balasto implemente completamente DALI Device Type 8. Usar **DT6** para todos los demas balastos CCT.

Las configuraciones de ejemplo para ambos tipos se encuentran en [`docs/examples/setup/`](docs/examples/setup/).

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

**Behaviors** determinan el valor de luz. La integracion utiliza dos behaviors de anulacion por target — uno para control de automatizacion (`/override/automation`) y otro para control manual (`/override/manual`).

**Destinations** determinan a donde se envia el valor calculado: `DALI` (salida al bus), `MESSAGING` (publicacion de estado MQTT), `HTTPSERVER` (consulta de estado HTTP).

---

## Seguimiento de contexto

Todos los cambios de estado realizados internamente por la integracion llevan el Context ID `picolightnode_internal`. Esto permite que blueprints externos (p. ej. Keyframe Scheduler) distingan entre acciones iniciadas por el usuario y actualizaciones internas de la integracion, lo que posibilita una deteccion fiable de anulaciones manuales.

---

## Integraciones relacionadas

| Integracion | Repositorio |
|-------------|-------------|
| Keyframe Scheduler | https://github.com/mjmijh/keyframe-scheduler |
| CCT Astronomy | https://github.com/mjmijh/cct-astronomy |

---

## Problemas y soporte

https://github.com/mjmijh/picolightnode-ha/issues
