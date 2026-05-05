# Research: Project Baseline

## Decision: Backend vigente unificado en FastAPI

**Decision**: Tratar `backend/api-backend` como backend activo y fuente de verdad.

**Rationale**: El código actual contiene `main.py`, routers REST, modelos SQLAlchemy, Alembic, handlers conversacionales y tests. Los documentos históricos que mencionan Django describen una fase anterior.

**Alternatives considered**:

- Mantener Django como parte de la arquitectura vigente: rechazado porque no hay backend Django activo en la estructura actual.
- Documentar ambos como equivalentes: rechazado porque crearía confusión y duplicaría decisiones.

## Decision: Spec Kit para brownfield

**Decision**: Usar Spec Kit no solo para features nuevas, sino también para documentar baseline del sistema existente.

**Rationale**: El proyecto está avanzado y necesita una fuente de verdad antes de seguir con cambios conversacionales.

**Alternatives considered**:

- Solo actualizar README: insuficiente para specs ejecutables y tareas futuras.
- Solo crear docs en `docs/`: no alinea el flujo con Spec Kit.

## Decision: Menú guiado como próxima feature

**Decision**: Crear `001-guided-menu-bot` como primera spec funcional posterior a la baseline.

**Rationale**: El riesgo actual está en interpretación conversacional y acciones ambiguas. Un menú guiado híbrido reduce errores y mantiene IA como apoyo.

**Alternatives considered**:

- Optimizar prompts primero: menos predecible y más costoso.
- Apagar IA por completo: perdería utilidad para fecha/hora y atajos naturales.
