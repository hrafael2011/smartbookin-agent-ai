<!-- SPECKIT START -->
For additional context about technologies to be used, project structure,
shell commands, and other important information, read the current Spec Kit
artifacts before implementing changes.

Primary context for this repository:

- `.specify/memory/constitution.md` defines non-negotiable project principles.
- `specs/000-project-baseline/` documents the current SmartBooking AI system.
- `specs/001-guided-menu-bot/` documents the next planned conversational phase.

Main rule: specs are the source of truth. If older docs conflict with
`specs/000-project-baseline/`, follow the baseline and update stale docs when
the change requires it.
<!-- SPECKIT END -->

## Registro obligatorio de tareas (WORKLOG)

**Toda** tarea, fix o cambio de infraestructura debe quedar anotado en
`docs/WORKLOG.md`. Es el mecanismo para que otra sesión —humano o agente— sepa
qué se hizo, qué falta y por qué.

Antes de empezar:

1. Lee `docs/WORKLOG.md` y busca tu tarea en *Backlog*.
2. Si ya existe, actualiza su estado en lugar de duplicarla.
3. Al terminar, añade una entrada en *Registro de cambios* (más reciente arriba)
   indicando **qué**, **dónde**, **por qué** y **cómo se verificó**.
4. Si la tarea se difiere, déjala en el *Backlog* con el motivo y la fecha.
   Nunca se borra una entrada.

Esto aplica igual a cambios de código que a cambios en Railway, Vercel o Neon.

