# 🎭 SmartBooking AI - Diagrama de Flujos Completos

## 📊 Resumen Ejecutivo

**Sistema:** WhatsApp Bot para agendamiento de citas con IA
**IA Engine:** GPT-4o-mini (OpenAI)
**Estado Actual:** 70% MVP completado (3/5 sprints)

---

## 🔄 FLUJO 1: Agendar Cita (Book Appointment)

```
┌─────────────────────────────────────────────────────────────────┐
│ 👤 Cliente: "Quiero un corte para mañana en la tarde"          │
└────────────────────┬────────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────────┐
│ 📨 WhatsApp Cloud API                                           │
│ POST → https://graph.facebook.com/v21.0/{phone_id}/messages     │
└────────────────────┬────────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────────┐
│ 🔐 Agent Service (FastAPI)                                      │
│ POST /webhooks/whatsapp                                         │
│                                                                 │
│ 1. Validar firma HMAC SHA256                                   │
│ 2. Extraer mensaje del payload                                 │
│ 3. Marcar como leído ✓                                         │
└────────────────────┬────────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────────┐
│ 💾 Redis - Obtener Contexto                                     │
│ GET redis:conversation:{business_id}:{phone_number}            │
│                                                                 │
│ Context = {                                                     │
│   "customer_id": 123,                                          │
│   "customer_name": "Carlos Méndez",                            │
│   "state": "idle",                                             │
│   "current_intent": null,                                      │
│   "recent_messages": [...],                                    │
│   "pending_data": {}                                           │
│ }                                                              │
└────────────────────┬────────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────────┐
│ 🤖 NLU Engine (GPT-4o-mini)                                     │
│ POST https://api.openai.com/v1/chat/completions                │
│                                                                 │
│ System Prompt:                                                  │
│ "Eres asistente de Barbería El Clásico..."                    │
│ + Business info (services, schedule, location)                 │
│ + Conversation context (last 10 messages)                      │
│                                                                 │
│ User Message: "Quiero un corte para mañana en la tarde"       │
│                                                                 │
│ Response:                                                       │
│ {                                                              │
│   "intent": "book_appointment",                                │
│   "confidence": 0.95,                                          │
│   "entities": {                                                │
│     "service": "corte",                                        │
│     "date": "2025-12-05",    // ← mañana normalizado          │
│     "time": "afternoon"       // ← tarde → preferencia        │
│   }                                                            │
│ }                                                              │
└────────────────────┬────────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────────┐
│ 🎯 Booking Handler                                              │
│ handle_book_appointment(nlu_result, context)                   │
│                                                                 │
│ PASO 1: Buscar servicio                                        │
│ ├─ GET /api/v1/services/?business_id=1&search=corte          │
│ └─ Encontrado: "Corte de Cabello" (id=1, 30min, RD$300)      │
└────────────────────┬────────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────────┐
│ 📅 Django Backend - Consultar Disponibilidad                    │
│ GET /api/v1/appointments/availability/                         │
│     ?business_id=1                                             │
│     &service_id=1                                              │
│     &date=2025-12-05                                           │
│     &preferred_time=afternoon                                  │
│                                                                 │
│ ⚙️  AvailabilityService.get_available_slots():                 │
│                                                                 │
│ 1. Consultar schedule_rules para el día viernes               │
│    ScheduleRule.filter(business=1, day_of_week=4)             │
│    → Viernes: 09:00 - 18:00                                   │
│                                                                 │
│ 2. Generar slots cada 30min (service.duration)                │
│    09:00, 09:30, 10:00, ..., 17:30                           │
│                                                                 │
│ 3. Verificar agenda global del owner                          │
│    Appointment.filter(                                         │
│      business__owner_id=1,                                     │
│      start_at__date='2025-12-05'                              │
│    )                                                           │
│    → Excluir slots ocupados                                   │
│                                                                 │
│ 4. Filtrar solo disponibles                                   │
│    → [14:00, 14:30, 15:00, 15:30, 16:00, 17:00]              │
│                                                                 │
│ 5. Marcar slots preferidos (cerca de 'afternoon')             │
│    → 14:00 (2 PM) ⭐ is_preferred = true                      │
│                                                                 │
│ Response:                                                       │
│ {                                                              │
│   "available_slots": [                                         │
│     {                                                          │
│       "start_time": "02:00 PM",                               │
│       "start_datetime": "2025-12-05T14:00:00-04:00",         │
│       "end_datetime": "2025-12-05T14:30:00-04:00",           │
│       "is_preferred": true                                    │
│     },                                                         │
│     { "start_time": "03:30 PM", ... },                        │
│     { "start_time": "05:00 PM", ... }                         │
│   ]                                                            │
│ }                                                              │
└────────────────────┬────────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────────┐
│ 💾 Redis - Actualizar Contexto                                 │
│ SET redis:conversation:{business_id}:{phone_number}            │
│ {                                                              │
│   "state": "awaiting_slot_selection",                         │
│   "current_intent": "book_appointment",                       │
│   "pending_data": {                                           │
│     "service_id": 1,                                          │
│     "service_name": "Corte de Cabello",                      │
│     "date": "2025-12-05",                                     │
│     "available_slots": [...]                                  │
│   }                                                            │
│ }                                                              │
│ TTL: 3600 segundos (1 hora)                                   │
└────────────────────┬────────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────────┐
│ 📤 Enviar Respuesta a WhatsApp                                  │
│ POST https://graph.facebook.com/v21.0/{phone_id}/messages      │
│                                                                 │
│ 🤖 Bot: "Perfecto, Carlos. Encontré estos horarios..."         │
│                                                                 │
│ 1️⃣ 02:00 PM ⭐ (recomendado)                                   │
│ 2️⃣ 03:30 PM                                                    │
│ 3️⃣ 05:00 PM                                                    │
│                                                                 │
│ ¿Cuál prefieres? Responde con el número.                      │
└─────────────────────────────────────────────────────────────────┘
                     │
                     │ 👤 Cliente: "El primero"
                     ▼
┌─────────────────────────────────────────────────────────────────┐
│ 🎯 Slot Selection Handler                                       │
│ handle_slot_selection(message, context)                        │
│                                                                 │
│ Detección flexible:                                            │
│ • "1" → slot index 0                                          │
│ • "primero", "primer" → slot index 0                          │
│ • "02:00 PM" → buscar en available_slots                     │
│                                                                 │
│ Selected: slots[0] = {                                         │
│   "start_datetime": "2025-12-05T14:00:00-04:00",             │
│   "end_datetime": "2025-12-05T14:30:00-04:00"                │
│ }                                                              │
└────────────────────┬────────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────────┐
│ 📝 Django Backend - Crear Appointment                          │
│ POST /api/v1/appointments/                                     │
│ {                                                              │
│   "business": 1,                                              │
│   "customer": 123,                                            │
│   "service": 1,                                               │
│   "start_at": "2025-12-05T14:00:00-04:00",                   │
│   "end_at": "2025-12-05T14:30:00-04:00",                     │
│   "status": "scheduled"                                       │
│ }                                                              │
│                                                                 │
│ ⚙️  AppointmentSerializer.validate():                          │
│ 1. ✓ Service belongs to business                              │
│ 2. ✓ Service is active                                        │
│ 3. ✓ Customer is active                                       │
│                                                                 │
│ ⚙️  AppointmentViewSet.create():                               │
│ AvailabilityService.validate_appointment_creation()            │
│ 1. ✓ Slot dentro de schedule_rules                           │
│ 2. ✓ No overlap en agenda del owner                          │
│ 3. ✓ Service duration coincide                               │
│                                                                 │
│ Response:                                                       │
│ {                                                              │
│   "id": 456,                                                  │
│   "status": "scheduled",                                      │
│   "start_at": "2025-12-05T14:00:00-04:00",                   │
│   "service_name": "Corte de Cabello",                        │
│   "business_name": "Barbería El Clásico"                     │
│ }                                                              │
└────────────────────┬────────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────────┐
│ 💾 Redis - Limpiar Contexto                                    │
│ {                                                              │
│   "state": "idle",                                            │
│   "current_intent": null,                                     │
│   "pending_data": {}  // ← Limpiado                          │
│ }                                                              │
└────────────────────┬────────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────────┐
│ 📤 Confirmación Final                                           │
│                                                                 │
│ 🤖 Bot: "✅ ¡Listo, Carlos! Tu cita está confirmada"           │
│                                                                 │
│ 📅 Viernes 5 de diciembre                                      │
│ ⏰ 02:00 PM                                                     │
│ ✂️ Corte de Cabello                                            │
│ 💰 RD$ 300                                                      │
│ 📍 Barbería El Clásico - Calle Principal #45                  │
│                                                                 │
│ Te enviaré recordatorios antes de tu cita 😊                  │
└─────────────────────────────────────────────────────────────────┘
```

---

## ❌ FLUJO 2: Cancelar Cita con Waitlist

```
┌─────────────────────────────────────────────────────────────────┐
│ 👤 Cliente: "Necesito cancelar mi cita del 15"                 │
└────────────────────┬────────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────────┐
│ 🤖 NLU Engine                                                   │
│ {                                                              │
│   "intent": "cancel_appointment",                              │
│   "confidence": 0.91,                                          │
│   "entities": {                                                │
│     "date": "2025-12-15"                                       │
│   }                                                            │
│ }                                                              │
└────────────────────┬────────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────────┐
│ 📋 Cancel Handler - PASO 1: Obtener citas                      │
│ GET /api/v1/customers/123/appointments/?upcoming=true          │
│                                                                 │
│ Appointments = [                                               │
│   { id: 456, date: "2025-12-05", service: "Corte" },         │
│   { id: 789, date: "2025-12-15", service: "Barba" }          │
│ ]                                                              │
└────────────────────┬────────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────────┐
│ 📋 Cancel Handler - PASO 2: Pedir confirmación                 │
│                                                                 │
│ Redis context:                                                  │
│ {                                                              │
│   "state": "awaiting_cancel_confirmation",                    │
│   "current_intent": "cancel_appointment",                     │
│   "pending_data": {                                           │
│     "appointment_id": 789                                     │
│   }                                                            │
│ }                                                              │
│                                                                 │
│ 🤖 Bot: "Tu cita:"                                             │
│ 📅 Lunes 15 de diciembre                                       │
│ ⏰ 04:00 PM                                                     │
│ ✂️ Afeitado y Barba                                            │
│                                                                 │
│ ¿Confirmas que quieres cancelarla?                            │
└─────────────────────────────────────────────────────────────────┘
                     │
                     │ 👤 Cliente: "Sí, por favor"
                     ▼
┌─────────────────────────────────────────────────────────────────┐
│ 📝 Django Backend - Cancelar                                   │
│ PATCH /api/v1/appointments/789/                                │
│ {                                                              │
│   "status": "cancelled",                                       │
│   "cancellation_notes": "Cancelado por cliente vía WhatsApp"  │
│ }                                                              │
│                                                                 │
│ Appointment.status = 'cancelled' ✓                             │
└────────────────────┬────────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────────┐
│ ⚡ Celery - Activar Waitlist (Asíncrono)                       │
│ notify_waitlist_task.delay(appointment_id=789)                 │
│                                                                 │
│ Task enviado a cola → Procesamiento en background              │
└────────────────────┬────────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────────┐
│ 🔍 Celery Worker - Buscar en Waitlist                          │
│                                                                 │
│ Query:                                                          │
│ WaitlistEntry.filter(                                          │
│   business_id=1,                                              │
│   service_id=2,              # Afeitado y Barba               │
│   preferred_date='2025-12-15',                                │
│   status='pending'                                            │
│ ).order_by('created_at')     # ← FIFO ordering                │
│                                                                 │
│ Encontrado:                                                     │
│ - María García (customer_id=456) ← Primera en fila            │
│ - Pedro López (customer_id=789)  ← Segunda en fila            │
└────────────────────┬────────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────────┐
│ ✉️  Enviar Oferta a María García                               │
│                                                                 │
│ WaitlistEntry.update(                                          │
│   status='offered',                                           │
│   offered_at=now()                                            │
│ )                                                              │
│                                                                 │
│ WhatsApp Message:                                              │
│ 🤖 Bot: "🎉 ¡Buenas noticias, María!"                          │
│                                                                 │
│ Se liberó un horario que solicitaste:                         │
│ 📅 Lunes 15 de diciembre                                       │
│ ⏰ 04:00 PM                                                     │
│ ✂️ Afeitado y Barba                                            │
│                                                                 │
│ ¿Te gustaría tomarlo?                                         │
│ Responde SÍ en los próximos 5 minutos.                       │
└─────────────────────────────────────────────────────────────────┘
                     │
                     │ Opción A: María responde "Sí" (en < 5 min)
                     ▼
┌─────────────────────────────────────────────────────────────────┐
│ ✅ María Acepta                                                 │
│                                                                 │
│ POST /api/v1/appointments/                                     │
│ {                                                              │
│   "business": 1,                                              │
│   "customer": 456,  # María                                   │
│   "service": 2,                                               │
│   "start_at": "2025-12-15T16:00:00-04:00",                   │
│   "status": "scheduled"                                       │
│ }                                                              │
│                                                                 │
│ WaitlistEntry.update(status='accepted')                        │
│                                                                 │
│ 🤖 Bot: "✅ ¡Perfecto, María! Tu cita está confirmada"         │
└─────────────────────────────────────────────────────────────────┘
                     │
                     │ Opción B: María no responde (> 5 min)
                     ▼
┌─────────────────────────────────────────────────────────────────┐
│ ⏱️ Celery Beat: process_waitlist_expirations (cada 1 minuto)  │
│                                                                 │
│ Query:                                                          │
│ WaitlistEntry.filter(                                          │
│   status='offered',                                           │
│   offered_at__lte=now() - timedelta(minutes=5)                │
│ )                                                              │
│                                                                 │
│ Encontrado: María's entry (más de 5 min sin respuesta)        │
│                                                                 │
│ WaitlistEntry.update(status='expired')                         │
│                                                                 │
│ → Ofrecer a siguiente: Pedro López                            │
│                                                                 │
│ 🤖 Bot a Pedro: "🎉 ¡Buenas noticias, Pedro!..."              │
└─────────────────────────────────────────────────────────────────┘
```

---

## 🔄 FLUJO 3: Reagendar Cita (Modify Appointment)

```
┌─────────────────────────────────────────────────────────────────┐
│ 👤 Cliente: "Necesito mover mi cita para el sábado"           │
└────────────────────┬────────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────────┐
│ 🤖 NLU Engine                                                   │
│ {                                                              │
│   "intent": "modify_appointment",                              │
│   "confidence": 0.89,                                          │
│   "entities": {                                                │
│     "date": "2025-12-06"  // sábado normalizado               │
│   }                                                            │
│ }                                                              │
└────────────────────┬────────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────────┐
│ 🔄 Modify Handler - ESTADO 1: Seleccionar cita                 │
│                                                                 │
│ GET /api/v1/customers/123/appointments/?upcoming=true          │
│                                                                 │
│ Si tiene 1 cita:                                               │
│   → Seleccionar automáticamente                               │
│                                                                 │
│ Si tiene múltiples:                                            │
│   → state = "awaiting_appointment_selection_modify"           │
│   → Mostrar lista numerada                                    │
│   → Esperar respuesta del cliente                             │
└────────────────────┬────────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────────┐
│ 🔄 Modify Handler - ESTADO 2: Obtener nueva fecha              │
│                                                                 │
│ Redis context:                                                  │
│ {                                                              │
│   "state": "awaiting_new_date",                               │
│   "pending_data": {                                           │
│     "selected_appointment_id": 456,                           │
│     "service_id": 1                                           │
│   }                                                            │
│ }                                                              │
│                                                                 │
│ 🤖 Bot: "¿Para qué día?"                                       │
│ (Ej: mañana, viernes, 10 de diciembre)                       │
└─────────────────────────────────────────────────────────────────┘
                     │
                     │ 👤 Cliente: "El sábado"
                     ▼
┌─────────────────────────────────────────────────────────────────┐
│ 🔄 Modify Handler - ESTADO 3: Obtener nueva hora               │
│                                                                 │
│ Redis context:                                                  │
│ {                                                              │
│   "state": "awaiting_new_time",                               │
│   "pending_data": {                                           │
│     "selected_appointment_id": 456,                           │
│     "service_id": 1,                                          │
│     "new_date": "2025-12-06"  // ← Guardado                  │
│   }                                                            │
│ }                                                              │
│                                                                 │
│ 🤖 Bot: "¿A qué hora prefieres?"                              │
│ (Ej: 3 PM, en la mañana, 15:00)                              │
└─────────────────────────────────────────────────────────────────┘
                     │
                     │ 👤 Cliente: "11 de la mañana"
                     ▼
┌─────────────────────────────────────────────────────────────────┐
│ 🔄 Modify Handler - ESTADO 4: Consultar disponibilidad         │
│                                                                 │
│ GET /api/v1/appointments/availability/                         │
│   ?date=2025-12-06                                             │
│   &service_id=1                                                │
│   &preferred_time=11:00                                        │
│                                                                 │
│ Available slots: [                                             │
│   { "start_time": "11:00 AM", is_preferred: true },          │
│   { "start_time": "11:30 AM" },                              │
│   { "start_time": "12:00 PM" }                               │
│ ]                                                              │
│                                                                 │
│ Redis context:                                                  │
│ {                                                              │
│   "state": "awaiting_slot_selection_modify",                  │
│   "pending_data": {                                           │
│     "selected_appointment_id": 456,                           │
│     "available_slots": [...]                                  │
│   }                                                            │
│ }                                                              │
│                                                                 │
│ 🤖 Bot: "Encontré estos horarios para sábado..."              │
│ 1️⃣ 11:00 AM ⭐                                                 │
│ 2️⃣ 11:30 AM                                                    │
│ 3️⃣ 12:00 PM                                                    │
└─────────────────────────────────────────────────────────────────┘
                     │
                     │ 👤 Cliente: "1"
                     ▼
┌─────────────────────────────────────────────────────────────────┐
│ 🔄 Modify Handler - ESTADO 5: Actualizar appointment           │
│                                                                 │
│ PATCH /api/v1/appointments/456/                                │
│ {                                                              │
│   "start_at": "2025-12-06T11:00:00-04:00",                   │
│   "end_at": "2025-12-06T11:30:00-04:00"                      │
│ }                                                              │
│                                                                 │
│ ⚙️  Validaciones:                                              │
│ 1. ✓ Nuevo slot está disponible                              │
│ 2. ✓ Dentro de schedule_rules                                │
│ 3. ✓ No overlap con otras citas                              │
│                                                                 │
│ Appointment actualizado ✓                                      │
│                                                                 │
│ Redis: Limpiar context (state='idle', pending_data={})        │
│                                                                 │
│ 🤖 Bot: "✅ ¡Listo! Tu cita se reagendó exitosamente"         │
│                                                                 │
│ 📅 Nueva fecha: sábado 6 de diciembre                         │
│ ⏰ Nueva hora: 11:00 AM                                        │
│ ✂️ Corte de Cabello                                            │
└─────────────────────────────────────────────────────────────────┘
```

---

## 🔔 FLUJO 4: Recordatorios Automáticos (Celery Beat)

```
╔═════════════════════════════════════════════════════════════════╗
║ 📅 Celery Beat Scheduler                                        ║
║ Corre en background 24/7                                        ║
╚═════════════════════════════════════════════════════════════════╝

┌─────────────────────────────────────────────────────────────────┐
│ ⏰ TAREA 1: send_reminder_24h                                   │
│ Frecuencia: Cada 15 minutos (crontab(minute='*/15'))          │
│                                                                 │
│ Query:                                                          │
│ Appointment.filter(                                            │
│   start_at__gte = now() + timedelta(hours=23, minutes=45)     │
│   start_at__lte = now() + timedelta(hours=24, minutes=15)     │
│   status__in = ['scheduled', 'confirmed']                      │
│ )                                                              │
│                                                                 │
│ Para cada appointment:                                          │
│   WhatsAppService.send_text_message_sync(                     │
│     to=customer.phone,                                         │
│     message=f"""                                               │
│       🔔 Recordatorio de cita                                  │
│                                                                 │
│       Hola {customer.name}, te recuerdo que mañana            │
│       tienes tu cita:                                         │
│                                                                 │
│       📅 {formatted_date}                                      │
│       ⏰ {formatted_time}                                      │
│       ✂️ {service.name}                                        │
│       📍 {business.name} - {business.address}                 │
│                                                                 │
│       ¡Te esperamos! 😊                                        │
│     """                                                        │
│   )                                                            │
│                                                                 │
│   Appointment.reminder_24h_sent = True                         │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│ ⏰ TAREA 2: send_reminder_2h                                    │
│ Frecuencia: Cada 5 minutos (crontab(minute='*/5'))            │
│                                                                 │
│ Query:                                                          │
│ Appointment.filter(                                            │
│   start_at__gte = now() + timedelta(hours=1, minutes=55)      │
│   start_at__lte = now() + timedelta(hours=2, minutes=5)       │
│   status__in = ['scheduled', 'confirmed'],                     │
│   reminder_2h_sent = False                                     │
│ )                                                              │
│                                                                 │
│ Para cada appointment:                                          │
│   WhatsAppService.send_interactive_buttons(                    │
│     to=customer.phone,                                         │
│     message=f"""                                               │
│       ⏰ Tu cita es en 2 horas                                 │
│                                                                 │
│       📅 Hoy, {formatted_time}                                 │
│       ✂️ {service.name}                                        │
│       📍 {business.name}                                       │
│                                                                 │
│       Por favor confirma tu asistencia:                       │
│     """,                                                       │
│     buttons=[                                                  │
│       {"id": "confirm", "title": "✅ Confirmar"},             │
│       {"id": "cancel", "title": "❌ Cancelar"},               │
│       {"id": "reschedule", "title": "📅 Reagendar"}           │
│     ]                                                          │
│   )                                                            │
│                                                                 │
│   Appointment.status = 'pending_confirmation'                  │
│   Appointment.reminder_2h_sent = True                          │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│ ⏱️  TAREA 3: process_waitlist_expirations                      │
│ Frecuencia: Cada 1 minuto (crontab(minute='*/1'))             │
│                                                                 │
│ Query:                                                          │
│ WaitlistEntry.filter(                                          │
│   status='offered',                                           │
│   offered_at__lte = now() - timedelta(minutes=5)              │
│ )                                                              │
│                                                                 │
│ Para cada entrada expirada:                                     │
│   1. Marcar como expirada                                     │
│      WaitlistEntry.status = 'expired'                         │
│                                                                 │
│   2. Buscar siguiente en fila (FIFO)                          │
│      next_entry = WaitlistEntry.filter(                       │
│        business_id = entry.business_id,                       │
│        service_id = entry.service_id,                         │
│        preferred_date = entry.preferred_date,                 │
│        status = 'pending'                                     │
│      ).order_by('created_at').first()                         │
│                                                                 │
│   3. Validar service.is_active y customer.is_active           │
│                                                                 │
│   4. Enviar nueva oferta                                      │
│      WhatsAppService.send_text_message_sync(...)              │
│      next_entry.status = 'offered'                            │
│      next_entry.offered_at = now()                            │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│ 📊 TAREA 4: send_daily_agenda                                   │
│ Frecuencia: Diaria a las 7:00 AM (crontab(hour=7, minute=0))  │
│                                                                 │
│ Query:                                                          │
│ businesses = Business.filter(owner_id=1)                       │
│                                                                 │
│ Para cada business:                                             │
│   appointments = Appointment.filter(                           │
│     business_id = business.id,                                │
│     start_at__date = today(),                                 │
│     status__in = ['scheduled', 'confirmed',                    │
│                   'pending_confirmation']                      │
│   ).order_by('start_at')                                      │
│                                                                 │
│   confirmed = appointments.filter(status='confirmed')          │
│   pending = appointments.filter(                               │
│     status='pending_confirmation'                             │
│   )                                                            │
│                                                                 │
│   recent_cancellations = Appointment.filter(                   │
│     business_id = business.id,                                │
│     status = 'cancelled',                                     │
│     updated_at__gte = today() - timedelta(days=1)             │
│   )                                                            │
│                                                                 │
│   WhatsAppService.send_text_message_sync(                     │
│     to = business.owner.phone,                                │
│     message = f"""                                            │
│       📊 **AGENDA DE HOY** - {formatted_date}                 │
│       {business.name}                                         │
│                                                                 │
│       ✅ **CONFIRMADAS ({len(confirmed)})**                    │
│       [lista de citas confirmadas]                            │
│                                                                 │
│       ⏰ **PENDIENTES DE CONFIRMAR ({len(pending)})**          │
│       [lista de citas pendientes]                             │
│                                                                 │
│       ❌ **CANCELACIONES RECIENTES**                           │
│       [lista de cancelaciones]                                │
│                                                                 │
│       📈 Ocupación: {occupancy}%                              │
│       💰 Ingresos proyectados: RD$ {projected_revenue}        │
│                                                                 │
│       ¡Que tengas un excelente día! 💼                        │
│     """                                                        │
│   )                                                            │
└─────────────────────────────────────────────────────────────────┘
```

---

## 🏗️ Arquitectura del Sistema

```
┌─────────────────────────────────────────────────────────────────┐
│                        WHATSAPP CLOUD API                        │
│                   (Meta Business Platform)                       │
└────────────────────────┬─────────────────────────────────────────┘
                         │
                         │ Webhook POST /webhooks/whatsapp
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│                     AGENT SERVICE (FastAPI)                      │
│                                                                  │
│  ┌──────────────┐  ┌─────────────┐  ┌──────────────────────┐  │
│  │   Webhook    │  │ NLU Engine  │  │   Conversation       │  │
│  │   Handler    │──│  (GPT-4o)   │  │   Manager            │  │
│  │              │  │             │  │  (State Machine)     │  │
│  └──────────────┘  └─────────────┘  └──────────────────────┘  │
│         │                 │                     │               │
│         │                 │                     │               │
│  ┌──────┴─────────────────┴─────────────────────┴───────────┐  │
│  │                     Handlers                              │  │
│  │  • booking_handler    • cancel_handler                    │  │
│  │  • check_handler      • modify_handler                    │  │
│  └───────────────────────────────────────────────────────────┘  │
└────────────────────┬──────────────────────┬─────────────────────┘
                     │                      │
                     │ HTTP REST            │ Redis
                     │                      │
          ┌──────────▼──────────┐     ┌─────▼─────────┐
          │  DJANGO BACKEND     │     │     REDIS     │
          │  (REST API)         │     │   (Context)   │
          │                     │     │   TTL: 1h     │
          │  • DRF ViewSets     │     └───────────────┘
          │  • Serializers      │
          │  • Business Logic   │
          │  • AvailabilityServ │
          └──────────┬──────────┘
                     │
                     │ PostgreSQL
                     │
          ┌──────────▼──────────┐
          │    POSTGRESQL       │
          │                     │
          │  Tables:            │
          │  • owners           │
          │  • businesses       │
          │  • services         │
          │  • schedule_rules   │
          │  • customers        │
          │  • appointments     │
          │  • waitlist_entries │
          └──────────┬──────────┘
                     │
          ┌──────────▼──────────┐
          │   CELERY + BEAT     │
          │                     │
          │  Tasks:             │
          │  • reminder_24h     │
          │  • reminder_2h      │
          │  • waitlist_exp     │
          │  • daily_agenda     │
          └─────────────────────┘
```

---

## 📊 Estado Actual del Proyecto

### ✅ Completado (70%)

#### Sprint 1: Backend API REST
- ✅ Modelos Django (7 modelos)
- ✅ Serializers DRF (10 serializers)
- ✅ ViewSets CRUD (6 viewsets)
- ✅ AvailabilityService (lógica de negocio)
- ✅ 40+ endpoints REST

#### Sprint 2: Agent Service Base
- ✅ FastAPI webhook handler
- ✅ NLU Engine con GPT-4o-mini
- ✅ Conversation Manager (Redis)
- ✅ WhatsApp Client (async/sync)
- ✅ Django Client (HTTP)

#### Sprint 3: Celery Tasks
- ✅ 4 tareas programadas
- ✅ Recordatorios automáticos
- ✅ Waitlist automation
- ✅ Agenda diaria para dueños

#### Sprint 4: Handlers Conversacionales
- ✅ booking_handler (agendar)
- ✅ check_handler (consultar)
- ✅ cancel_handler (cancelar)
- ✅ modify_handler (reagendar)

### ⬜ Pendiente (30%)

#### Sprint 5: Frontend Panel Web
- ⬜ Setup (React + Vite + TypeScript)
- ⬜ Autenticación JWT
- ⬜ Dashboard con métricas
- ⬜ Calendario de citas
- ⬜ CRUD de servicios
- ⬜ Gestión de clientes
- ⬜ Configuración de horarios

---

## 🚀 Tecnologías Implementadas

| Componente | Tecnología | Propósito |
|------------|-----------|-----------|
| **Backend API** | Django + DRF | REST API, business logic |
| **Agent Service** | FastAPI | Webhook WhatsApp, NLU |
| **IA Engine** | GPT-4o-mini | Intent extraction, entity recognition |
| **Cache** | Redis | Conversation context (TTL 1h) |
| **Database** | PostgreSQL | Persistent data storage |
| **Task Queue** | Celery + Beat | Automated tasks, cron jobs |
| **Message Broker** | Redis | Celery backend |
| **WhatsApp API** | Meta Cloud API | Message delivery |
| **Orchestration** | Docker Compose | Multi-container deployment |

---

## 📈 Métricas del Sistema

- **Endpoints REST:** 40+
- **Modelos Django:** 7
- **Serializers:** 10
- **Conversation Handlers:** 4
- **Celery Tasks:** 4 (programadas)
- **Estados conversacionales:** 15+
- **Intents soportados:** 5 (book, check, cancel, modify, business_info)
- **Context TTL:** 1 hora (Redis)
- **Waitlist timeout:** 5 minutos
- **Reminder windows:** 24h y 2h antes

---

*Generado por SmartBooking AI - Demo System*
