# ADR-002: Hybrid Orchestrator (Menú Guiado + NLU) sobre NLU Puro

- **Estado:** Aceptado
- **Fecha:** 2026-06-26
- **Decidido por:** [Tu nombre]

## Contexto

El sistema debe interpretar mensajes de clientes en español a través de WhatsApp y Telegram para agendar, cancelar, modificar y consultar citas.

Existían dos enfoques para el motor conversacional:
1. **NLU Puro** — cada mensaje se envía al LLM para clasificar intención y extraer entidades
2. **Híbrido** — menú guiado determinístico primero, NLU solo como fallback

## Decisión

Elegimos **Hybrid Orchestrator.** El mensaje entrante primero se verifica contra el menú activo o el capability router (determinístico, 0ms de latencia). Si el routing determinístico no puede clasificar el mensaje con seguridad, se escala al NLU Engine (GPT-4o-mini).

## Alternativas consideradas

### NLU Puro (descartado)

**Ventajas:**
- Simple — un solo path de procesamiento
- Flexible — el usuario puede expresarse libremente

**Desventajas:**
- Latencia de API (~500ms-1s por mensaje)
- Costo por mensaje ($0.00015/token)
- Alucinaciones en frases ambiguas (fechas malinterpretadas, servicios inexistentes)
- Sin funcionamiento offline o sin conectividad a API

### Híbrido (elegido)

Este patrón está formalizado en la [constitución del proyecto](.specify/memory/constitution.md) (Sección IV: "Guided Conversation First"):

1. Si hay un flujo activo, el `ConversationState` decide cómo interpretar
2. Si el estado es `idle`, el menú guiado decide primero
3. NLU se usa solo después de que el routing determinístico falla
4. La ejecución siempre termina en handlers y servicios, nunca en la salida del LLM

**Ventajas:**
- El ~80% de interacciones se resuelven por menú (0ms de latencia, $0 de costo)
- NLU solo para interacciones no estructuradas (~20%)
- Menor costo operacional (~80% menos llamadas a OpenAI)
- Experiencia más rápida para el usuario
- Funciona incluso si la API de OpenAI no está disponible (los menús siguen operativos)

**Desventajas:**
- Dos paths de código que mantener (menú + NLU)
- Los menús deben diseñarse bien para cubrir los casos de uso comunes

## Consecuencias

- **Positivo:** ~80% de mensajes sin costo de LLM
- **Positivo:** Respuesta instantánea en selecciones de menú
- **Positivo:** El sistema sigue funcionando si OpenAI no está disponible
- **Negativo:** Duplicación de lógica de routing (menú determinístico + NLU)
- **Negativo:** La experiencia conversacional puede sentirse más rígida cuando el menú atrapa mensajes que podrían ser NLU
