# Quickstart: Validar Bot Con Menú Guiado Híbrido

## Preparación

Levantar stack local según `specs/000-project-baseline/quickstart.md`.

Para pruebas automáticas rápidas:

```bash
./scripts/verify-mvp.sh backend-conversation
```

Para salida completa de backend:

```bash
./scripts/verify-mvp.sh backend-all
```

## Escenarios Manuales

### Menú sin IA

Enviar en WhatsApp o Telegram:

```text
hola
```

Resultado esperado: menú numerado.

Validación automática relacionada:

```bash
./scripts/verify-mvp.sh backend-conversation
```

### Opción de agendar

Enviar:

```text
1
```

Resultado esperado: lista de servicios o mensaje de no servicios.

### Atajo natural

Enviar:

```text
quiero cita mañana a las 10
```

Resultado esperado: entra a flujo de agendamiento y solicita el dato guiado faltante. No crea cita.

### Horarios

Enviar:

```text
qué horario tienen
```

Resultado esperado: responde horarios/ubicación o dirige a opción `5`, sin inventar datos.

### Navegación Universal

Durante un flujo activo enviar:

```text
9
```

Resultado esperado: vuelve al menú anterior o, en la primera implementación, al menú principal sin ejecutar acciones.

Enviar:

```text
0
```

Resultado esperado: limpia el flujo activo y muestra menú principal.

Enviar:

```text
x
```

Resultado esperado: cierra la consulta activa y deja la conversación en `idle`.

### Ambiguo

Enviar:

```text
eso mismo para mañana
```

Resultado esperado: menú o pregunta guiada. No acción.

### Grosero o fuera de dominio

Enviar un insulto o pregunta no relacionada.

Resultado esperado: límite breve y menú. No acción.

### Inactividad

Dejar una conversación en flujo activo por más de 30 minutos y enviar cualquier mensaje.

Resultado esperado: el sistema cierra el flujo anterior por inactividad, limpia datos temporales y muestra el menú principal.

### Confirmación Crítica

Intentar crear, cancelar o modificar una cita mediante atajo natural.

Resultado esperado: el sistema puede interpretar intención/datos, pero no ejecuta la acción final sin confirmación explícita del usuario.
