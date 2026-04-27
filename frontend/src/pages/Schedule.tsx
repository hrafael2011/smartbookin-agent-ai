import { useEffect, useMemo, useState } from 'react';
import { CalendarDays, Clock, RotateCcw, Save, Trash2 } from 'lucide-react';
import { toast } from 'sonner';
import { Badge, Button, Card, CardContent, CardHeader, CardTitle, EmptyState, Input } from '@/components/ui';
import { scheduleAPI } from '@/services/api';
import { useBusinessStore } from '@/store/businessStore';
import {
  ScheduleException,
  ScheduleExceptionFormData,
  ScheduleFormData,
  ScheduleRule,
} from '@/types';

const DAYS_OF_WEEK = [
  { value: 0, label: 'Domingo', shortLabel: 'Dom' },
  { value: 1, label: 'Lunes', shortLabel: 'Lun' },
  { value: 2, label: 'Martes', shortLabel: 'Mar' },
  { value: 3, label: 'Miércoles', shortLabel: 'Mié' },
  { value: 4, label: 'Jueves', shortLabel: 'Jue' },
  { value: 5, label: 'Viernes', shortLabel: 'Vie' },
  { value: 6, label: 'Sábado', shortLabel: 'Sáb' },
];

interface DaySchedule {
  day_of_week: number;
  is_available: boolean;
  start_time: string;
  end_time: string;
}

const DEFAULT_EXCEPTION_FORM: ScheduleExceptionFormData = {
  date: '',
  type: 'block',
  all_day: true,
  start_time: '09:00',
  end_time: '18:00',
  reason: '',
};

export function Schedule() {
  const { currentBusiness } = useBusinessStore();
  const [schedules, setSchedules] = useState<DaySchedule[]>([]);
  const [exceptions, setExceptions] = useState<ScheduleException[]>([]);
  const [exceptionForm, setExceptionForm] = useState<ScheduleExceptionFormData>(
    DEFAULT_EXCEPTION_FORM
  );
  const [showArchived, setShowArchived] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [isSaving, setIsSaving] = useState<number | null>(null);
  const [isSavingException, setIsSavingException] = useState(false);
  const [exceptionActionId, setExceptionActionId] = useState<number | null>(null);

  useEffect(() => {
    if (currentBusiness) {
      void loadSchedules();
      void loadExceptions();
    }
  }, [currentBusiness]);

  const visibleExceptions = useMemo(
    () => (showArchived ? exceptions : exceptions.filter((item) => !item.deleted_at)),
    [exceptions, showArchived]
  );

  const loadSchedules = async () => {
    if (!currentBusiness) return;
    setIsLoading(true);
    try {
      const data = await scheduleAPI.list(currentBusiness.id);

      const scheduleMap = new Map<number, ScheduleRule>();
      data.forEach((rule: ScheduleRule) => {
        scheduleMap.set(rule.day_of_week, rule);
      });

      const allDays = DAYS_OF_WEEK.map((day) => {
        const existing = scheduleMap.get(day.value);
        return {
          day_of_week: day.value,
          is_available: existing?.is_available ?? true,
          start_time: existing?.start_time ?? '09:00',
          end_time: existing?.end_time ?? '18:00',
        };
      });

      setSchedules(allDays);
    } catch (error) {
      console.error('Error loading schedules:', error);
      toast.error('No se pudieron cargar los horarios');
    } finally {
      setIsLoading(false);
    }
  };

  const loadExceptions = async () => {
    if (!currentBusiness) return;
    try {
      const data = await scheduleAPI.listExceptions(currentBusiness.id, {
        includeDeleted: true,
      });
      setExceptions(
        [...data].sort((a, b) => {
          const byDate = a.date.localeCompare(b.date);
          if (byDate !== 0) return byDate;
          if (a.all_day !== b.all_day) return a.all_day ? -1 : 1;
          return (a.start_time || '').localeCompare(b.start_time || '');
        })
      );
    } catch (error) {
      console.error('Error loading schedule exceptions:', error);
      toast.error('No se pudieron cargar las excepciones');
    }
  };

  const handleToggleDay = (dayIndex: number) => {
    setSchedules((prev) =>
      prev.map((schedule, idx) =>
        idx === dayIndex
          ? { ...schedule, is_available: !schedule.is_available }
          : schedule
      )
    );
  };

  const handleTimeChange = (
    dayIndex: number,
    field: 'start_time' | 'end_time',
    value: string
  ) => {
    setSchedules((prev) =>
      prev.map((schedule, idx) =>
        idx === dayIndex ? { ...schedule, [field]: value } : schedule
      )
    );
  };

  const handleSaveDay = async (dayIndex: number) => {
    const schedule = schedules[dayIndex];
    setIsSaving(dayIndex);

    try {
      if (!currentBusiness) return;
      if (schedule.is_available && schedule.start_time >= schedule.end_time) {
        toast.error('La hora de inicio debe ser anterior a la hora de cierre');
        return;
      }
      const formData: ScheduleFormData = {
        day_of_week: schedule.day_of_week,
        is_available: schedule.is_available,
        start_time: schedule.start_time,
        end_time: schedule.end_time,
      };

      await scheduleAPI.create({ ...formData, business: currentBusiness.id });
      await loadSchedules();
      toast.success(`Horario de ${DAYS_OF_WEEK[dayIndex].label} guardado correctamente`);
    } catch (error) {
      console.error('Error saving schedule:', error);
      toast.error('Error al guardar el horario');
    } finally {
      setIsSaving(null);
    }
  };

  const handleExceptionFieldChange = (
    field: keyof ScheduleExceptionFormData,
    value: string | boolean
  ) => {
    setExceptionForm((prev) => ({ ...prev, [field]: value }));
  };

  const handleSaveException = async () => {
    if (!currentBusiness) return;
    if (!exceptionForm.date) {
      toast.error('Selecciona una fecha para la excepción');
      return;
    }

    setIsSavingException(true);
    try {
      await scheduleAPI.createException({
        business: currentBusiness.id,
        date: exceptionForm.date,
        type: exceptionForm.type,
        all_day: exceptionForm.all_day,
        start_time: exceptionForm.all_day ? undefined : exceptionForm.start_time,
        end_time: exceptionForm.all_day ? undefined : exceptionForm.end_time,
        reason: exceptionForm.reason?.trim() || undefined,
      });

      await loadExceptions();
      setExceptionForm(DEFAULT_EXCEPTION_FORM);
      toast.success('Excepción guardada correctamente');
    } catch (error: any) {
      console.error('Error creating schedule exception:', error);
      const detail = error?.response?.data?.detail;
      toast.error(typeof detail === 'string' ? detail : 'Error al guardar la excepción');
    } finally {
      setIsSavingException(false);
    }
  };

  const handleArchiveException = async (exceptionId: number) => {
    setExceptionActionId(exceptionId);
    try {
      await scheduleAPI.archiveException(exceptionId);
      await loadExceptions();
      toast.success('Excepción archivada');
    } catch (error: any) {
      console.error('Error archiving schedule exception:', error);
      toast.error(error?.response?.data?.detail || 'No se pudo archivar la excepción');
    } finally {
      setExceptionActionId(null);
    }
  };

  const handleRestoreException = async (exceptionId: number) => {
    setExceptionActionId(exceptionId);
    try {
      await scheduleAPI.restoreException(exceptionId);
      await loadExceptions();
      toast.success('Excepción restaurada');
    } catch (error: any) {
      console.error('Error restoring schedule exception:', error);
      toast.error(error?.response?.data?.detail || 'No se pudo restaurar la excepción');
    } finally {
      setExceptionActionId(null);
    }
  };

  const formatExceptionDate = (value: string) =>
    new Date(value + 'T00:00:00').toLocaleDateString('es-DO', {
      weekday: 'long',
      year: 'numeric',
      month: 'long',
      day: 'numeric',
    });

  const formatExceptionRange = (item: ScheduleException) => {
    if (item.all_day) return 'Día completo';
    return `${item.start_time || '--:--'} - ${item.end_time || '--:--'}`;
  };

  if (isLoading) {
    return (
      <div className="p-6 flex items-center justify-center">
        <div className="text-muted-foreground">Cargando horarios...</div>
      </div>
    );
  }

  return (
    <div className="p-6 space-y-6">
      <div>
        <h1 className="text-3xl font-bold text-foreground">Configuración de Horarios</h1>
        <p className="text-muted-foreground mt-2">
          Define tu horario semanal y bloquea o abre días específicos desde calendario
        </p>
      </div>

      <div className="grid gap-4">
        {schedules.map((schedule, index) => {
          const dayInfo = DAYS_OF_WEEK[index];

          return (
            <Card key={dayInfo.value}>
              <CardContent className="p-6">
                <div className="flex flex-col md:flex-row md:items-center gap-4 md:gap-6">
                  <div className="w-full md:w-32">
                    <div className="flex items-center gap-3">
                      <input
                        type="checkbox"
                        id={`day-${dayInfo.value}`}
                        checked={schedule.is_available}
                        onChange={() => handleToggleDay(index)}
                        className="h-5 w-5 rounded border-gray-300"
                      />
                      <label
                        htmlFor={`day-${dayInfo.value}`}
                        className="text-base font-medium text-foreground cursor-pointer"
                      >
                        {dayInfo.label}
                      </label>
                    </div>
                  </div>

                  {schedule.is_available ? (
                    <div className="flex flex-col sm:flex-row sm:items-center gap-4 flex-1">
                      <div className="flex items-center gap-3 flex-1">
                        <Clock className="h-4 w-4 text-muted-foreground hidden sm:block" />
                        <div className="flex flex-wrap items-center gap-2">
                          <Input
                            type="time"
                            value={schedule.start_time}
                            onChange={(e) =>
                              handleTimeChange(index, 'start_time', e.target.value)
                            }
                            className="w-full sm:w-32"
                          />
                          <span className="hidden sm:inline text-muted-foreground">a</span>
                          <Input
                            type="time"
                            value={schedule.end_time}
                            onChange={(e) => handleTimeChange(index, 'end_time', e.target.value)}
                            className="w-full sm:w-32"
                          />
                        </div>
                      </div>

                      <Button
                        onClick={() => handleSaveDay(index)}
                        isLoading={isSaving === index}
                        size="sm"
                        className="w-full sm:w-auto"
                      >
                        <Save className="h-4 w-4 mr-2" />
                        Guardar
                      </Button>
                    </div>
                  ) : (
                    <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 flex-1">
                      <Badge variant="default" className="w-fit bg-muted text-muted-foreground">
                        Cerrado
                      </Badge>
                      <Button
                        onClick={() => handleSaveDay(index)}
                        isLoading={isSaving === index}
                        size="sm"
                        className="w-full sm:w-auto"
                      >
                        <Save className="h-4 w-4 mr-2" />
                        Guardar
                      </Button>
                    </div>
                  )}
                </div>
              </CardContent>
            </Card>
          );
        })}
      </div>

      <Card>
        <CardHeader className="flex flex-col md:flex-row md:items-center md:justify-between gap-3">
          <CardTitle className="flex items-center gap-2">
            <CalendarDays className="h-5 w-5 text-primary" />
            Excepciones por Fecha
          </CardTitle>
          <Button
            variant={showArchived ? 'secondary' : 'outline'}
            size="sm"
            onClick={() => setShowArchived((prev) => !prev)}
          >
            {showArchived ? 'Ocultar archivadas' : 'Mostrar archivadas'}
          </Button>
        </CardHeader>
        <CardContent className="space-y-6">
          <div className="grid grid-cols-1 md:grid-cols-6 gap-3">
            <Input
              label="Fecha"
              type="date"
              value={exceptionForm.date}
              onChange={(e) => handleExceptionFieldChange('date', e.target.value)}
            />

            <div className="w-full">
              <label className="block text-sm font-semibold text-foreground mb-2">Tipo</label>
              <select
                value={exceptionForm.type}
                onChange={(e) =>
                  handleExceptionFieldChange(
                    'type',
                    e.target.value as ScheduleExceptionFormData['type']
                  )
                }
                className="flex h-11 w-full rounded-lg border-2 border-input bg-background px-4 py-2 text-sm transition-all duration-200 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/20 focus-visible:border-primary hover:border-primary/40"
              >
                <option value="block">Bloquear</option>
                <option value="open">Abrir excepcionalmente</option>
              </select>
            </div>

            <div className="w-full md:col-span-2 flex items-end">
              <label className="inline-flex items-center gap-2 text-sm font-medium text-foreground">
                <input
                  type="checkbox"
                  checked={exceptionForm.all_day}
                  onChange={(e) => handleExceptionFieldChange('all_day', e.target.checked)}
                  className="h-4 w-4 rounded border-gray-300"
                />
                Día completo
              </label>
            </div>

            {!exceptionForm.all_day && (
              <>
                <Input
                  label="Desde"
                  type="time"
                  value={exceptionForm.start_time}
                  onChange={(e) => handleExceptionFieldChange('start_time', e.target.value)}
                />
                <Input
                  label="Hasta"
                  type="time"
                  value={exceptionForm.end_time}
                  onChange={(e) => handleExceptionFieldChange('end_time', e.target.value)}
                />
              </>
            )}
          </div>

          <Input
            label="Motivo (opcional)"
            value={exceptionForm.reason || ''}
            onChange={(e) => handleExceptionFieldChange('reason', e.target.value)}
            placeholder="Ej: feriado, mantenimiento, evento privado"
          />

          <div className="flex justify-end">
            <Button onClick={handleSaveException} isLoading={isSavingException}>
              <Save className="h-4 w-4 mr-2" />
              Guardar excepción
            </Button>
          </div>

          <div className="space-y-3">
            {visibleExceptions.length === 0 ? (
              <EmptyState
                icon={<CalendarDays className="h-6 w-6" />}
                title="Sin excepciones por ahora"
                description="Agrega cierres por feriados, vacaciones o aperturas especiales cuando lo necesites."
              />
            ) : (
              visibleExceptions.map((item) => (
                <div
                  key={item.id}
                  className="rounded-lg border border-border/60 p-4 flex flex-col md:flex-row md:items-center md:justify-between gap-3"
                >
                  <div className="space-y-1">
                    <div className="flex items-center gap-2 flex-wrap">
                      <Badge variant={item.type === 'block' ? 'destructive' : 'success'}>
                        {item.type === 'block' ? 'Bloqueo' : 'Apertura'}
                      </Badge>
                      {item.deleted_at ? <Badge variant="outline">Archivada</Badge> : null}
                    </div>
                    <div className="text-sm font-semibold text-foreground">
                      {formatExceptionDate(item.date)}
                    </div>
                    <div className="text-sm text-muted-foreground">
                      {formatExceptionRange(item)}
                      {item.reason ? ` · ${item.reason}` : ''}
                    </div>
                  </div>

                  <div className="flex items-center gap-2">
                    {item.deleted_at ? (
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => handleRestoreException(item.id)}
                        isLoading={exceptionActionId === item.id}
                      >
                        <RotateCcw className="h-4 w-4 mr-1" />
                        Restaurar
                      </Button>
                    ) : (
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => handleArchiveException(item.id)}
                        isLoading={exceptionActionId === item.id}
                      >
                        <Trash2 className="h-4 w-4 mr-1" />
                        Archivar
                      </Button>
                    )}
                  </div>
                </div>
              ))
            )}
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Información</CardTitle>
        </CardHeader>
        <CardContent>
          <ul className="space-y-2 text-sm text-muted-foreground">
            <li>• El horario semanal define tu disponibilidad base</li>
            <li>• Las excepciones por fecha tienen prioridad sobre el horario semanal</li>
            <li>• Usa “Bloquear” para cierres puntuales y “Abrir” para horarios especiales</li>
            <li>• Al archivar una excepción, se conserva el historial (soft delete)</li>
          </ul>
        </CardContent>
      </Card>
    </div>
  );
}
