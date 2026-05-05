# Research: Bot Con Menú Guiado Híbrido

## Decision: Texto numerado como interfaz principal

**Decision**: Usar texto numerado para menú y listas.

**Rationale**: WhatsApp limita botones interactivos a pocos botones y Telegram tiene capacidades distintas. Texto numerado mantiene paridad y simplifica pruebas.

**Alternatives considered**:

- Botones siempre: rechazado por límites y diferencias entre canales.
- Botones donde se pueda: útil luego, pero añade ramas de UX en fase 1.

## Decision: IA como intérprete, no ejecutora

**Decision**: La IA solo produce señales de intención/datos. Los handlers ejecutan.

**Rationale**: Reduce errores de negocio, evita acciones no confirmadas y preserva auditabilidad.

**Alternatives considered**:

- IA como router principal: rechazado por baja predictibilidad.
- Menú estricto sin IA: rechazado porque empeora atajos naturales útiles como fecha/hora.

## Decision: Menú global solo en `idle`

**Decision**: Las opciones `1` a `5` se tratan como menú global únicamente cuando `ConversationState.state == idle`.

**Rationale**: Dentro de flujos activos, los números ya significan servicio, horario o cita.

**Alternatives considered**:

- Permitir menú global siempre: rompe selección de listas.
- Requerir palabra `menu` para salir: puede añadirse, pero no debe bloquear selecciones activas.

## Decision: Fallback profesional para abuso y fuera de dominio

**Decision**: Responder con límite breve y menú.

**Rationale**: Mantiene tono profesional, evita discusiones y reduce consumo IA.

**Alternatives considered**:

- Ignorar mensajes: puede parecer roto.
- Respuesta generada por IA: innecesaria y riesgosa.
