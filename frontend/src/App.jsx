import { useEffect, useMemo, useRef, useState } from "react";
import React from "react";
import { api } from "./api";

const TZ = "America/Argentina/Cordoba";
const MIN_BOOKING_NOTICE_MINUTES = 20;
const ANY_BARBER = "any";
const ALL_BARBERS = "all";
const BUSINESS_NAME = "Marcelo Navarro";
const RESERVATION_STEPS = ["barber", "service", "date", "time", "details"];
const SERVICE_FILTERS = {
  active: "Activos",
  inactive: "Inactivos",
  all: "Todos",
};

function todayISO() {
  return new Intl.DateTimeFormat("en-CA", { timeZone: TZ }).format(new Date());
}

function parseLocalDate(iso) {
  const [year, month, day] = iso.split("-").map(Number);
  return new Date(year, month - 1, day);
}

function formatDate(iso, weekday = true) {
  return new Intl.DateTimeFormat("es-AR", {
    weekday: weekday ? "long" : undefined,
    day: "numeric",
    month: "long",
    timeZone: TZ,
  }).format(parseLocalDate(iso));
}

function isOpenDay(iso) {
  const day = parseLocalDate(iso).getDay();
  return day >= 2 && day <= 6;
}

function timeLabel(value) {
  return `${String(value).slice(0, 5)} hs.`;
}

function formatPrice(value) {
  if (value === null || value === undefined) return "A consultar";
  const amount = Number(value || 0);
  return `$ ${new Intl.NumberFormat("es-AR", { maximumFractionDigits: 0 }).format(amount)}`;
}

function formatServicePrice(service) {
  if (!service || service.price === null || service.price === undefined || service.has_consultation_price) return "A consultar";
  const price = formatPrice(service?.price);
  return service?.is_from_price ? `Desde ${price}` : price;
}

function formatDuration(value) {
  if (value === null || value === undefined) return "A consultar";
  return `${value} min`;
}

function formatAdminMinutes(value) {
  if (value === null || value === undefined || value === "") return "No configurado";
  return `${value} min`;
}

function formatServiceDuration(service) {
  if (!service) return "A consultar";
  if (service.duration_depends_on_professional) return "La duración depende del profesional";
  if (service.duration_visible_minutes === null || service.duration_visible_minutes === undefined) return "A consultar";
  return formatDuration(service.duration_visible_minutes);
}

function formatDepositSummary(service) {
  if (!service?.requires_deposit) return null;
  const deposit = service.deposit_amount;
  const balance = service.remaining_balance;
  return {
    depositLabel: deposit === null || deposit === undefined ? "Seña a confirmar" : formatPrice(deposit),
    balanceLabel: balance === null || balance === undefined ? "Saldo a consultar" : formatPrice(balance),
  };
}

function serviceMetaLabel(service) {
  const price = formatServicePrice(service);
  const duration = formatServiceDuration(service);
  if (price === "A consultar" || duration === "A consultar") {
    return (
      <>
        <span>Precio: {price}</span>
        <span>Duración: {duration}</span>
      </>
    );
  }
  return <span>{price} · {duration}</span>;
}

function cancellationLink(token) {
  return `${window.location.origin}/cancelar/${encodeURIComponent(token)}`;
}

function normalizePhoneInput(value) {
  return String(value || "").replace(/\D/g, "");
}

function isValidPhoneInput(value) {
  const raw = String(value || "").trim();
  if (!raw) return false;
  if (/[^\d\s\-()]/.test(raw)) return false;
  return /^\d{10,11}$/.test(normalizePhoneInput(raw));
}

function prepareArgentineWhatsAppPhone(phone) {
  let digits = normalizePhoneInput(phone);
  if (digits.startsWith("0")) digits = digits.slice(1);
  if (digits.startsWith("549")) return digits;
  if (digits.startsWith("54")) return `549${digits.slice(2)}`;
  if (digits.length === 10) return `549${digits}`;
  return digits;
}

function bookingCancellationLink(booking) {
  return booking?.cancellation_token ? cancellationLink(booking.cancellation_token) : "";
}

function whatsappMessage(booking) {
  const link = bookingCancellationLink(booking);
  return [
    `Hola ${booking.client_first_name}.`,
    "",
    `Tu turno en ${BUSINESS_NAME} fue confirmado.`,
    "",
    `Peluquero: ${displayBarberName(booking.barber_name)}`,
    `Servicio: ${booking.service_name}`,
    `Precio: ${formatPrice(booking.service_price)}`,
    booking.deposit_amount !== null && booking.deposit_amount !== undefined ? `Seña abonada: ${formatPrice(booking.deposit_amount)}` : null,
    booking.remaining_balance !== null && booking.remaining_balance !== undefined ? `Saldo en el salón: ${formatPrice(booking.remaining_balance)}` : null,
    `Duración: ${formatDuration(booking.service_visible_duration_minutes)}`,
    `Fecha: ${formatDate(booking.date)}`,
    `Hora: ${timeLabel(booking.start_time)}`,
    "",
    "Para cancelar tu turno:",
    link,
  ].filter((line) => line !== null).join("\n");
}

function whatsappUrl(booking) {
  const message = whatsappMessage(booking);
  const encodedMessage = encodeURIComponent(message);
  const whatsappPhone = prepareArgentineWhatsAppPhone(booking.client_phone);
  return `https://api.whatsapp.com/send?phone=${whatsappPhone}&text=${encodedMessage}`;
}

function cancellationTokenFromPath() {
  const match = window.location.pathname.match(/^\/cancelar\/([^/]+)\/?$/);
  return match ? decodeURIComponent(match[1]) : null;
}

function paymentReturnFromPath() {
  const match = window.location.pathname.match(/^\/pago\/(exito|pendiente|error)\/?$/);
  const params = new URLSearchParams(window.location.search);
  if (!match) return null;
  return {
    result: match[1],
    token: params.get("token") || "",
    paymentId: params.get("payment_id") || params.get("collection_id") || "",
  };
}

function currentMinutesInArgentina() {
  const parts = new Intl.DateTimeFormat("en-US", {
    timeZone: TZ,
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  }).formatToParts(new Date());
  const hour = Number(parts.find((part) => part.type === "hour")?.value || 0);
  const minute = Number(parts.find((part) => part.type === "minute")?.value || 0);
  return hour * 60 + minute;
}

function slotMinutes(value) {
  const [hour, minute] = String(value).slice(0, 5).split(":").map(Number);
  return hour * 60 + minute;
}

function isBookableSlot(iso, slot) {
  if (iso !== todayISO()) return true;
  return slotMinutes(slot) >= currentMinutesInArgentina() + MIN_BOOKING_NOTICE_MINUTES;
}

function dateOptions() {
  const base = parseLocalDate(todayISO());
  return Array.from({ length: 14 }, (_, index) => {
    const date = new Date(base);
    date.setDate(base.getDate() + index);
    return new Intl.DateTimeFormat("en-CA").format(date);
  });
}

function firstOpenDate() {
  return dateOptions().find(isOpenDay) || todayISO();
}

function initials(name) {
  return String(name || "?")
    .split(" ")
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part[0])
    .join("")
    .toUpperCase();
}

function displayBarberName(name) {
  if (!name) return "-";
  return name;
}

function barberById(barbers, barberId) {
  return barbers.find((item) => item.id === Number(barberId));
}

function selectedBarberName(barbers, barberId) {
  if (barberId === ANY_BARBER) return "Sin preferencia";
  return barberById(barbers, barberId)?.name || "-";
}

function appointmentServiceLabel(appointment) {
  if (!appointment) return "-";
  const payment = appointment.payment_status ? ` · Pago: ${appointment.payment_status}` : "";
  const deposit = appointment.deposit_amount !== null && appointment.deposit_amount !== undefined ? ` · Seña: ${formatPrice(appointment.deposit_amount)}` : "";
  return `${appointment.service_name} · ${formatPrice(appointment.service_price)} · Duración: ${formatDuration(appointment.service_visible_duration_minutes)} · Ocupa: ${formatDuration(appointment.service_blocking_duration_minutes)}${deposit}${payment}`;
}

function pluralize(value, singular, plural) {
  return `${value} ${value === 1 ? singular : plural}`;
}

function reservationStepNumber(step) {
  const index = RESERVATION_STEPS.indexOf(step);
  return index >= 0 ? index + 1 : 0;
}

function BarberAvatar({ barber, name, size = "sm" }) {
  const displayName = barber?.name || displayBarberName(name);
  const photoUrl = barber?.photo_url || "";
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    setFailed(false);
  }, [photoUrl]);

  return (
    <span className={`barber-avatar ${size}`} aria-label={displayName}>
      {!failed && photoUrl ? <img src={photoUrl} alt={displayName} onError={() => setFailed(true)} /> : <span>{initials(displayName)}</span>}
    </span>
  );
}

function BarberLabel({ barber, name }) {
  const displayName = barber?.name || displayBarberName(name);
  return (
    <span className="barber-label">
      <BarberAvatar barber={barber} name={displayName} />
      <span>{displayName}</span>
    </span>
  );
}

function Summary({ barber, service, date, time, customer, phone }) {
  const barberName = barber ? displayBarberName(barber) : "";
  return (
    <div className="summary">
      {barber ? <div><span>Peluquero</span><strong><BarberLabel name={barberName} /></strong></div> : null}
      <div><span>Servicio</span><strong>{service?.name || "-"}</strong></div>
      <div><span>Precio</span><strong>{formatServicePrice(service)}</strong></div>
      <div><span>Duración</span><strong>{formatServiceDuration(service)}</strong></div>
      <div><span>Fecha</span><strong>{date ? formatDate(date) : "-"}</strong></div>
      <div><span>Hora</span><strong>{time ? timeLabel(time) : "-"}</strong></div>
      {customer ? <div><span>Cliente</span><strong>{customer}</strong></div> : null}
      {phone ? <div><span>Teléfono</span><strong>{phone}</strong></div> : null}
    </div>
  );
}

export default function App() {
  const [view, setView] = useState("client");
  const [step, setStep] = useState("welcome");
  const [barbers, setBarbers] = useState([]);
  const [services, setServices] = useState([]);
  const [barberId, setBarberId] = useState(null);
  const [serviceId, setServiceId] = useState(null);
  const [date, setDate] = useState(firstOpenDate());
  const [available, setAvailable] = useState([]);
  const [availabilityKey, setAvailabilityKey] = useState("");
  const [loadingAvailability, setLoadingAvailability] = useState(false);
  const [availabilityError, setAvailabilityError] = useState("");
  const [availabilityRetry, setAvailabilityRetry] = useState(0);
  const availabilityRequestRef = useRef("");
  const [time, setTime] = useState(null);
  const [client, setClient] = useState({ first_name: "", last_name: "", phone: "" });
  const [booking, setBooking] = useState(null);
  const [bookingPending, setBookingPending] = useState(false);
  const confirmationDialogRef = useRef(null);
  const [copyMessage, setCopyMessage] = useState("");
  const [error, setError] = useState("");
  const [token, setToken] = useState(localStorage.getItem("adminToken") || "");
  const [login, setLogin] = useState({ username: "admin", password: "" });
  const [adminSection, setAdminSection] = useState("agenda");
  const [adminDate, setAdminDate] = useState(firstOpenDate());
  const [adminBarberTab, setAdminBarberTab] = useState(null);
  const [agenda, setAgenda] = useState([]);
  const [manual, setManual] = useState(null);
  const [manualServices, setManualServices] = useState([]);
  const [adminServices, setAdminServices] = useState([]);
  const [serviceSearch, setServiceSearch] = useState("");
  const [serviceFilter, setServiceFilter] = useState("active");
  const [serviceForm, setServiceForm] = useState(null);
  const [serviceConfirm, setServiceConfirm] = useState(null);
  const [serviceSaving, setServiceSaving] = useState(false);
  const [serviceMessage, setServiceMessage] = useState("");
  const [configBarberId, setConfigBarberId] = useState(null);
  const [barberServiceConfigs, setBarberServiceConfigs] = useState([]);
  const [barberServiceSearch, setBarberServiceSearch] = useState("");
  const [barberServiceForm, setBarberServiceForm] = useState(null);
  const [barberServiceConfirm, setBarberServiceConfirm] = useState(null);
  const [barberServiceSaving, setBarberServiceSaving] = useState(false);
  const [barberServiceMessage, setBarberServiceMessage] = useState("");
  const [quickServiceConfig, setQuickServiceConfig] = useState(null);
  const [quickServiceItems, setQuickServiceItems] = useState([]);
  const [quickConfigLoading, setQuickConfigLoading] = useState(false);
  const [cancelToken] = useState(cancellationTokenFromPath());
  const [paymentReturn] = useState(paymentReturnFromPath());
  const [paymentStatus, setPaymentStatus] = useState(null);
  const [paymentStatusState, setPaymentStatusState] = useState(paymentReturn ? "loading" : "idle");
  const [paymentStatusError, setPaymentStatusError] = useState("");
  const [cancelAppointmentData, setCancelAppointmentData] = useState(null);
  const [cancelStatus, setCancelStatus] = useState("loading");
  const [cancelError, setCancelError] = useState("");
  const phoneError = client.phone && !isValidPhoneInput(client.phone) ? "Ingresá un teléfono válido de 10 u 11 números." : "";
  const selectedService = services.find((item) => item.id === Number(serviceId));
  const selectedDepositSummary = formatDepositSummary(selectedService);
  const currentBarberName = selectedBarberName(barbers, barberId);
  const visibleAvailable = useMemo(
    () => available.filter((slot) => isBookableSlot(date, slot)),
    [available, date]
  );
  const visibleAgenda = useMemo(
    () => adminBarberTab === ALL_BARBERS ? agenda : agenda.filter((slot) => slot.barber_id === Number(adminBarberTab)),
    [agenda, adminBarberTab]
  );
  const groupedAgenda = useMemo(
    () => barbers.map((barber) => ({ barber, slots: agenda.filter((slot) => slot.barber_id === barber.id) })),
    [agenda, barbers]
  );
  const visibleAdminServices = useMemo(() => {
    const query = serviceSearch.trim().toLowerCase();
    return adminServices.filter((service) => {
      const matchesSearch = !query || service.name.toLowerCase().includes(query);
      const matchesFilter =
        serviceFilter === "all" ||
        (serviceFilter === "active" && service.active) ||
        (serviceFilter === "inactive" && !service.active);
      return matchesSearch && matchesFilter;
    });
  }, [adminServices, serviceFilter, serviceSearch]);
  const selectedConfigBarber = useMemo(
    () => barberById(barbers, configBarberId),
    [barbers, configBarberId]
  );
  const visibleBarberServiceConfigs = useMemo(() => {
    const query = barberServiceSearch.trim().toLowerCase();
    return barberServiceConfigs.filter((item) => {
      if (!query) return true;
      return [
        item.service_name,
        item.service_category,
        item.service_description,
      ].filter(Boolean).some((value) => value.toLowerCase().includes(query));
    });
  }, [barberServiceConfigs, barberServiceSearch]);
  const activeBarbers = useMemo(() => barbers.filter((barber) => barber.active !== false), [barbers]);
  const isReservationFlow = view === "client" && RESERVATION_STEPS.includes(step);
  const currentReservationStep = reservationStepNumber(step);
  const reservationProgress = currentReservationStep ? `${currentReservationStep * 20}%` : "0%";

  useEffect(() => {
    api.services().then(setServices).catch((err) => setError(err.message));
    api.barbers().then(setBarbers).catch((err) => setError(err.message));
  }, []);

  useEffect(() => {
    if (!barberId) return;
    const queryBarber = barberId === ANY_BARBER ? null : barberId;
    api.services(queryBarber).then(setServices).catch((err) => setError(err.message));
  }, [barberId]);

  useEffect(() => {
    if (!adminBarberTab && barbers.length) setAdminBarberTab(String(barbers[0].id));
  }, [adminBarberTab, barbers]);

  useEffect(() => {
    if (!cancelToken) return;
    api.cancellationDetails(cancelToken)
      .then((data) => {
        setCancelAppointmentData(data);
        setCancelStatus("ready");
        setCancelError("");
      })
      .catch((err) => {
        setCancelStatus("error");
        setCancelError(err.message);
      });
  }, [cancelToken]);

  useEffect(() => {
    if (!paymentReturn?.token) return;
    setPaymentStatusState("loading");
    api.paymentStatus(paymentReturn.token, paymentReturn.paymentId)
      .then((data) => {
        setPaymentStatus(data);
        setPaymentStatusState("ready");
        setPaymentStatusError("");
      })
      .catch((err) => {
        setPaymentStatusState("error");
        setPaymentStatusError(err.message);
      });
  }, [paymentReturn]);

  useEffect(() => {
    if (step === "time" && date) {
      const queryBarber = barberId === ANY_BARBER ? null : barberId;
      const nextAvailabilityKey = `${date}:${queryBarber || ANY_BARBER}:${serviceId}`;
      if (availabilityKey === nextAvailabilityKey) return;
      const requestKey = `${nextAvailabilityKey}:${availabilityRetry}`;
      availabilityRequestRef.current = requestKey;
      setLoadingAvailability(true);
      setAvailabilityError("");
      api.availability(date, queryBarber, serviceId)
        .then((slots) => {
          if (availabilityRequestRef.current !== requestKey) return;
          setAvailable(slots);
          setAvailabilityKey(nextAvailabilityKey);
          setAvailabilityError("");
        })
        .catch(() => {
          if (availabilityRequestRef.current !== requestKey) return;
          setAvailable([]);
          setAvailabilityError("No pudimos cargar los horarios. Intentá nuevamente.");
        })
        .finally(() => {
          if (availabilityRequestRef.current === requestKey) {
            setLoadingAvailability(false);
          }
        });
    }
  }, [step, date, barberId, serviceId, availabilityKey, availabilityRetry]);

  useEffect(() => {
    if (view === "admin" && token) refreshAgenda();
  }, [view, token, adminDate]);

  useEffect(() => {
    if (view === "admin" && token && adminSection === "services") loadAdminServices();
  }, [view, token, adminSection]);

  useEffect(() => {
    if (view === "admin" && token && adminSection === "barberServices" && !configBarberId && barbers.length) {
      setConfigBarberId(String(barbers[0].id));
    }
  }, [view, token, adminSection, configBarberId, barbers]);

  useEffect(() => {
    if (view === "admin" && token && adminSection === "barberServices" && configBarberId) {
      loadBarberServiceConfigs(configBarberId);
    }
  }, [view, token, adminSection, configBarberId]);

  useEffect(() => {
    if (view === "admin") {
      api.services().then(setServices).catch((err) => setError(err.message));
    }
  }, [view]);

  useEffect(() => {
    if (!manual?.barber_id) {
      setManualServices([]);
      return;
    }
    api.services(manual.barber_id)
      .then((items) => {
        setManualServices(items);
        setManual((current) => {
          if (!current || String(current.barber_id) !== String(manual.barber_id)) return current;
          if (items.some((service) => String(service.id) === String(current.service_id))) return current;
          return { ...current, service_id: items[0]?.id || "" };
        });
      })
      .catch((err) => setError(err.message));
  }, [manual?.barber_id]);

  const stats = useMemo(() => ({
    free: visibleAgenda.filter((slot) => slot.status === "Libre").length,
    booked: visibleAgenda.filter((slot) => slot.status === "Reservado").length,
    blocked: visibleAgenda.filter((slot) => slot.status === "Bloqueado").length,
  }), [visibleAgenda]);

  async function refreshAgenda() {
    try {
      setAgenda((await api.agenda(adminDate)).map((slot) => ({
        ...slot,
        barber_name: displayBarberName(slot.barber_name),
        appointment: slot.appointment ? { ...slot.appointment, barber_name: displayBarberName(slot.appointment.barber_name) } : slot.appointment,
      })));
    } catch (err) {
      setError(err.message);
    }
  }

  async function loadAdminServices() {
    try {
      setAdminServices(await api.adminServices());
    } catch (err) {
      setError(err.message);
    }
  }

  async function loadBarberServiceConfigs(nextBarberId = configBarberId) {
    if (!nextBarberId) return;
    try {
      setBarberServiceConfigs(await api.adminBarberServices(nextBarberId));
    } catch (err) {
      setError(err.message);
    }
  }

  function showCopyFeedback(message) {
    setCopyMessage(message);
    window.setTimeout(() => setCopyMessage(""), 2500);
  }

  function openNewServiceForm() {
    setServiceMessage("");
    setServiceForm({ mode: "create", name: "", description: "", category: "", active: true });
  }

  function openEditServiceForm(service) {
    setServiceMessage("");
    setServiceForm({
      mode: "edit",
      id: service.id,
      name: service.name,
      description: service.description || "",
      category: service.category || "",
      active: service.active,
    });
  }

  async function loadQuickServiceConfig(service) {
    if (!service) return;
    setQuickServiceConfig(service);
    setQuickConfigLoading(true);
    setBarberServiceMessage("");
    try {
      const responses = await Promise.all(activeBarbers.map(async (barber) => {
        const items = await api.adminBarberServices(barber.id);
        return {
          barber,
          item: items.find((config) => Number(config.service_id) === Number(service.id)),
        };
      }));
      setQuickServiceItems(responses.filter((entry) => entry.item).map(({ barber, item }) => ({ ...item, barber_id: barber.id, barber_name: barber.name })));
    } catch (err) {
      setError(err.message);
    } finally {
      setQuickConfigLoading(false);
    }
  }

  function openBarberServiceForm(item) {
    setBarberServiceMessage("");
    const formBarber = item.barber_id ? barberById(barbers, item.barber_id) : selectedConfigBarber;
    setBarberServiceForm({
      mode: item.assigned ? "edit" : "assign",
      barber_id: item.barber_id || configBarberId,
      barber_name: item.barber_name || formBarber?.name || "",
      service_id: item.service_id,
      service_name: item.service_name,
      price: item.price ?? "",
      priceConsultation: item.price === null || item.price === undefined,
      duration_visible_minutes: item.duration_visible_minutes ?? "",
      durationConsultation: item.duration_visible_minutes === null || item.duration_visible_minutes === undefined,
      blocking_duration_minutes: item.blocking_duration_minutes || selectedConfigBarber?.appointment_interval_minutes || 20,
      active: item.assigned ? item.active : true,
    });
  }

  function barberServicePayload(form) {
    return {
      ...(form.mode === "assign" ? { service_id: Number(form.service_id) } : {}),
      price: form.priceConsultation ? null : String(form.price),
      duration_visible_minutes: form.durationConsultation ? null : Number(form.duration_visible_minutes),
      blocking_duration_minutes: Number(form.blocking_duration_minutes),
      active: form.active,
    };
  }

  async function submitBarberServiceForm(event) {
    event.preventDefault();
    const targetBarberId = barberServiceForm?.barber_id || configBarberId;
    if (!barberServiceForm || barberServiceSaving || !targetBarberId) return;
    setBarberServiceSaving(true);
    setError("");
    setBarberServiceMessage("");
    try {
      const payload = barberServicePayload(barberServiceForm);
      if (barberServiceForm.mode === "assign") {
        await api.assignBarberService(targetBarberId, payload);
        setBarberServiceMessage(`Servicio asignado a ${barberServiceForm.barber_name || "profesional"}.`);
      } else {
        await api.updateBarberService(targetBarberId, barberServiceForm.service_id, payload);
        setBarberServiceMessage("Configuración actualizada.");
      }
      setBarberServiceForm(null);
      if (configBarberId) await loadBarberServiceConfigs(configBarberId);
      if (quickServiceConfig) await loadQuickServiceConfig(quickServiceConfig);
      await loadAdminServices();
    } catch (err) {
      setError(err.message);
    } finally {
      setBarberServiceSaving(false);
    }
  }

  async function confirmBarberServiceStatusChange() {
    const targetBarberId = barberServiceConfirm?.barber_id || configBarberId;
    if (!barberServiceConfirm || barberServiceSaving || !targetBarberId) return;
    setBarberServiceSaving(true);
    setError("");
    setBarberServiceMessage("");
    try {
      await api.updateBarberServiceStatus(targetBarberId, barberServiceConfirm.service_id, { active: !barberServiceConfirm.active });
      const barberName = barberServiceConfirm.barber_name || selectedConfigBarber?.name || "el profesional";
      setBarberServiceMessage(barberServiceConfirm.active ? `Servicio desactivado para ${barberName}.` : `Servicio reactivado para ${barberName}.`);
      setBarberServiceConfirm(null);
      if (configBarberId) await loadBarberServiceConfigs(configBarberId);
      if (quickServiceConfig) await loadQuickServiceConfig(quickServiceConfig);
      await loadAdminServices();
    } catch (err) {
      setError(err.message);
    } finally {
      setBarberServiceSaving(false);
    }
  }

  async function submitServiceForm(event) {
    event.preventDefault();
    if (!serviceForm || serviceSaving) return;
    setServiceSaving(true);
    setError("");
    setServiceMessage("");
    const payload = {
      name: serviceForm.name,
      description: serviceForm.description || null,
      category: serviceForm.category || null,
      active: serviceForm.active,
    };
    try {
      if (serviceForm.mode === "edit") {
        await api.updateAdminService(serviceForm.id, payload);
        setServiceMessage("Servicio actualizado.");
      } else {
        await api.createAdminService(payload);
        setServiceMessage("Servicio creado. Para que aparezca en reservas, asignalo a un profesional en la configuración de servicios por peluquero.");
      }
      setServiceForm(null);
      await loadAdminServices();
    } catch (err) {
      setError(err.message);
    } finally {
      setServiceSaving(false);
    }
  }

  async function confirmServiceStatusChange() {
    if (!serviceConfirm || serviceSaving) return;
    setServiceSaving(true);
    setError("");
    setServiceMessage("");
    try {
      await api.updateAdminServiceStatus(serviceConfirm.id, { active: !serviceConfirm.active });
      setServiceMessage(serviceConfirm.active ? "Servicio desactivado." : "Servicio reactivado.");
      setServiceConfirm(null);
      await loadAdminServices();
    } catch (err) {
      setError(err.message);
    } finally {
      setServiceSaving(false);
    }
  }

  async function submitBooking(event) {
    event.preventDefault();
    if (bookingPending) return;
    setError("");
    setCopyMessage("");
    if (!isValidPhoneInput(client.phone)) {
      setError("Ingresá un teléfono válido de 10 u 11 números.");
      return;
    }
    setBookingPending(true);
    try {
      const saved = await api.createAppointment({
        barber_id: barberId === ANY_BARBER ? null : Number(barberId),
        service_id: Number(serviceId),
        date,
        start_time: time,
        client: {
          ...client,
          phone: normalizePhoneInput(client.phone),
        },
      });
      const appointment = saved.appointment || saved;
      setBooking({
        ...appointment,
        creation_status: saved.status || appointment.status,
        cancellation_token: saved.cancellation_token || appointment.cancellation_token,
        deposit_amount: saved.deposit_amount ?? appointment.deposit_amount,
        remaining_balance: saved.remaining_balance ?? appointment.remaining_balance,
        payment_expires_at: saved.expires_at ?? appointment.payment_expires_at,
        payment_status_token: saved.payment_status_token,
        checkout_url: saved.checkout_url,
      });
      setStep("confirmation");
    } catch (err) {
      setError(err.message);
      setStep("time");
      setLoadingAvailability(true);
      setAvailabilityKey("");
      setAvailabilityRetry((value) => value + 1);
    } finally {
      setBookingPending(false);
    }
  }

  async function submitLogin(event) {
    event.preventDefault();
    setError("");
    try {
      const response = await api.login(login);
      localStorage.setItem("adminToken", response.access_token);
      setToken(response.access_token);
    } catch (err) {
      setError(err.message);
    }
  }

  async function submitManual(event) {
    event.preventDefault();
    if (!manual) return;
    setError("");
    try {
      await api.createManualAppointment({
        barber_id: Number(manual.barber_id),
        service_id: Number(manual.service_id),
        date: adminDate,
        start_time: manual.time,
        client: {
          first_name: manual.first_name,
          last_name: manual.last_name || "Sin apellido",
          phone: manual.phone || "Sin telefono",
        },
      });
      setManual(null);
      refreshAgenda();
    } catch (err) {
      setError(err.message);
    }
  }

  async function blockSlot(slot) {
    await api.blockSlot({ date: adminDate, start_time: slot.time, reason: "Bloqueado por administrador" });
    refreshAgenda();
  }

  async function cancelAppointment(slot) {
    await api.cancelAppointment(slot.appointment.id);
    refreshAgenda();
  }

  async function unblockSlot(slot) {
    await api.unblockSlot(slot.block_id);
    refreshAgenda();
  }

  function resetAvailabilityState(loading = false) {
    availabilityRequestRef.current = "";
    setAvailable([]);
    setAvailabilityKey("");
    setAvailabilityError("");
    setLoadingAvailability(loading);
  }

  function goBackToBarber() {
    setServiceId(null);
    setDate(null);
    setTime(null);
    resetAvailabilityState();
    setStep("barber");
  }

  function goBackToService() {
    setDate(null);
    setTime(null);
    resetAvailabilityState();
    setStep("service");
  }

  function goBackToDate() {
    setTime(null);
    setAvailabilityError("");
    setStep("date");
  }

  function goBackToTime() {
    setAvailabilityError("");
    setStep("time");
  }

  function resetClient() {
    setStep("welcome");
    setBarberId(null);
    setServiceId(null);
    setDate(firstOpenDate());
    setTime(null);
    resetAvailabilityState();
    setClient({ first_name: "", last_name: "", phone: "" });
    setBooking(null);
    setCopyMessage("");
    setError("");
  }

  async function copyCancellationLink() {
    const link = bookingCancellationLink(booking);
    if (!link) return;
    if (navigator.clipboard) {
      await navigator.clipboard.writeText(link);
      showCopyFeedback("Enlace copiado");
    }
  }

  function openWhatsAppConfirmation() {
    if (!booking) return;
    const enteredPhone = booking.client_phone;
    const normalizedPhone = normalizePhoneInput(enteredPhone);
    const whatsappPhone = prepareArgentineWhatsAppPhone(enteredPhone);
    const finalUrl = whatsappUrl(booking);
    console.log("WhatsApp confirmation link", {
      telefonoIngresado: enteredPhone,
      telefonoNormalizado: normalizedPhone,
      telefonoWhatsApp: whatsappPhone,
      urlFinal: finalUrl,
    });
    window.open(finalUrl, "_blank", "noopener,noreferrer");
  }

  function closeConfirmationModal() {
    resetClient();
  }

  async function openMercadoPagoCheckout() {
    if (!booking?.checkout_url && booking?.payment_status_token) {
      try {
        const response = await api.startPayment(booking.id, booking.payment_status_token);
        setBooking((current) => current ? { ...current, checkout_url: response.checkout_url } : current);
        window.location.href = response.checkout_url;
      } catch (err) {
        setError(err.message);
      }
      return;
    }
    if (booking?.checkout_url) {
      window.location.href = booking.checkout_url;
    }
  }

  async function confirmPublicCancellation() {
    if (!cancelToken) return;
    setCancelError("");
    try {
      await api.cancelByToken(cancelToken);
      setCancelStatus("cancelled");
    } catch (err) {
      setCancelStatus("error");
      setCancelError(err.message);
    }
  }

  function renderAgendaRows(slots) {
    return slots.map((slot) => {
      const barber = barberById(barbers, slot.barber_id);
      return (
        <div key={`${slot.barber_id}-${slot.time}`} className={`agenda-row ${slot.status === "Libre" ? "free" : slot.status === "Bloqueado" ? "blocked" : "booked"}`}>
          <strong>{String(slot.time).slice(0, 5)}</strong>
          <span>{slot.appointment?.end_time ? String(slot.appointment.end_time).slice(0, 5) : "-"}</span>
          <span><BarberLabel barber={barber} name={slot.barber_name} /></span>
          <span>{slot.appointment ? `${slot.appointment.client_first_name} ${slot.appointment.client_last_name}` : slot.status === "Bloqueado" ? "Horario bloqueado" : "Disponible"}</span>
          <span>{appointmentServiceLabel(slot.appointment)}</span>
          <span className={`status ${slot.status === "Libre" ? "free" : slot.status === "Bloqueado" ? "blocked" : "booked"}`}>{slot.appointment?.origin === "MANUAL" ? "Registrado manualmente" : slot.status}</span>
          <div className="row-actions">
            {slot.status === "Libre" && <><button onClick={() => setManual({ time: slot.time, barber_id: slot.barber_id, service_id: "", first_name: "", last_name: "", phone: "" })}>Registrar</button><button onClick={() => blockSlot(slot)}>Bloquear</button></>}
            {(slot.status === "Reservado" || slot.status === "Pendiente de pago") && <button onClick={() => cancelAppointment(slot)}>Cancelar</button>}
            {slot.status === "Bloqueado" && <button onClick={() => unblockSlot(slot)}>Desbloquear</button>}
          </div>
        </div>
      );
    });
  }

  if (cancelToken) {
    return (
      <div className="shell">
        <header className="topbar">
          <button className="brand" onClick={() => { window.location.href = "/"; }} aria-label="Volver al inicio">
            <span className="logo-slot"><img src="/marcelo-navarro-logo.png" alt="Marcelo Navarro Peluqueria Unisex" /></span>
            <span><strong>Marcelo Navarro</strong><small>Turnos cada 20 min</small></span>
          </button>
        </header>

        <main>
          <section className="confirmation cancellation-page">
            {cancelStatus === "loading" ? (
              <>
                <p className="eyebrow">Cancelación de turno</p>
                <h2>Buscando tu turno</h2>
              </>
            ) : null}

            {cancelStatus === "ready" && cancelAppointmentData ? (
              <>
                <p className="eyebrow">Cancelación de turno</p>
                <h2>Confirmar cancelación</h2>
                <Summary
                  barber={cancelAppointmentData.barber_name}
                  service={{
                    name: cancelAppointmentData.service_name,
                    price: cancelAppointmentData.service_price,
                    duration_visible_minutes: cancelAppointmentData.service_visible_duration_minutes,
                  }}
                  date={cancelAppointmentData.date}
                  time={cancelAppointmentData.start_time}
                />
                <p className="lead cancel-question">¿Estás seguro de que querés cancelar este turno?</p>
                <div className="confirmation-actions">
                  <button className="primary" onClick={confirmPublicCancellation}>Cancelar turno</button>
                  <button className="ghost" onClick={() => { window.location.href = "/"; }}>Volver</button>
                </div>
              </>
            ) : null}

            {cancelStatus === "cancelled" ? (
              <>
                <div className="success-mark">OK</div>
                <h2>Tu turno fue cancelado correctamente.</h2>
                <p className="lead cancel-question">El horario fue liberado para que otra persona pueda reservarlo.</p>
                <button className="primary" onClick={() => { window.location.href = "/"; }}>Volver</button>
              </>
            ) : null}

            {cancelStatus === "error" ? (
              <>
                <p className="eyebrow">Cancelación de turno</p>
                <h2>{cancelError === "El turno ya fue cancelado." ? "Este turno ya fue cancelado." : "El enlace de cancelación no es válido o ya no está disponible."}</h2>
                <button className="primary" onClick={() => { window.location.href = "/"; }}>Volver</button>
              </>
            ) : null}
          </section>
        </main>
      </div>
    );
  }

  if (paymentReturn) {
    const confirmed = paymentStatus?.appointment_status === "CONFIRMED";
    const pending = paymentStatus?.appointment_status === "PENDING_PAYMENT" || paymentStatus?.payment_status === "PENDING";
    const expired = paymentStatus?.appointment_status === "EXPIRED";
    return (
      <div className="shell">
        <header className="topbar">
          <button className="brand" onClick={() => { window.location.href = "/"; }} aria-label="Volver al inicio">
            <span className="logo-slot"><img src="/marcelo-navarro-logo.png" alt="Marcelo Navarro Peluqueria Unisex" /></span>
            <span><strong>Marcelo Navarro</strong><small>Turnos cada 20 min</small></span>
          </button>
        </header>

        <main>
          <section className="confirmation payment-page">
            {paymentStatusState === "loading" ? (
              <>
                <p className="eyebrow">Pago de seña</p>
                <h2>Estamos verificando tu pago...</h2>
              </>
            ) : null}

            {paymentStatusState === "ready" && paymentStatus ? (
              <>
                <p className="eyebrow">Pago de seña</p>
                <div className="success-mark">{confirmed ? "OK" : pending ? "..." : "!"}</div>
                <h2>
                  {confirmed
                    ? "Pago recibido. Tu turno está confirmado."
                    : expired
                      ? "La reserva venció."
                      : pending
                        ? "Estamos verificando tu pago."
                        : "No pudimos confirmar el pago."}
                </h2>
                {!confirmed ? <p className="lead cancel-question">La llegada desde Mercado Pago no confirma el turno por sí sola. Estamos usando el estado real del sistema.</p> : null}
                <Summary
                  barber={paymentStatus.barber_name}
                  service={{ name: paymentStatus.service_name }}
                  date={paymentStatus.date}
                  time={paymentStatus.start_time}
                />
                {paymentStatus.deposit_amount !== null && paymentStatus.deposit_amount !== undefined ? (
                  <div className="deposit-preview confirmed-deposit">
                    <span>Seña: {formatPrice(paymentStatus.deposit_amount)}</span>
                    <span>Saldo a abonar en el salón: {formatPrice(paymentStatus.remaining_balance)}</span>
                    {paymentStatus.expires_at ? <p>Retención hasta: {new Date(paymentStatus.expires_at).toLocaleString("es-AR")}</p> : null}
                  </div>
                ) : null}
                <div className="confirmation-actions">
                  {pending && paymentStatus.checkout_url ? (
                    <button className="primary" onClick={() => { window.location.href = paymentStatus.checkout_url; }}>Volver a Mercado Pago</button>
                  ) : null}
                  <button className="ghost" onClick={() => { window.location.href = "/"; }}>Volver al inicio</button>
                </div>
              </>
            ) : null}

            {paymentStatusState === "error" ? (
              <>
                <p className="eyebrow">Pago de seña</p>
                <h2>No pudimos verificar el pago.</h2>
                <p className="lead cancel-question">{paymentStatusError || "El enlace no es válido o ya no está disponible."}</p>
                <button className="primary" onClick={() => { window.location.href = "/"; }}>Volver</button>
              </>
            ) : null}
          </section>
        </main>
      </div>
    );
  }

  return (
    <div className={isReservationFlow ? "shell flow-shell" : "shell"}>
      {!isReservationFlow ? (
      <header className="topbar">
        <button className="brand" onClick={() => { setView("client"); resetClient(); }} aria-label="Volver al inicio">
          <span className="logo-slot"><img src="/marcelo-navarro-logo.png" alt="Marcelo Navarro Peluqueria Unisex" /></span>
          <span><strong>Marcelo Navarro</strong><small>Turnos cada 20 min</small></span>
        </button>
        <nav className="nav-tabs" aria-label="Secciones">
          <button className={`tab ${view === "client" ? "active" : ""}`} onClick={() => setView("client")}>Reservar</button>
          <button className={`tab ${view === "admin" ? "active" : ""}`} onClick={() => setView("admin")}>Admin</button>
        </nav>
      </header>
      ) : null}

      {error ? <p className="error global-error">{error}</p> : null}

      {view === "client" ? (
        <main className={isReservationFlow ? "reservation-main" : undefined}>
          {step === "welcome" && (
            <section className="hero active">
              <div className="hero-copy">
                <p className="eyebrow">Agenda online</p>
                <h1>Reservá tu próximo corte.</h1>
                <p className="lead">Elegí peluquero, servicio, fecha y horario disponible.</p>
                <button className="primary cta" onClick={() => setStep("barber")}>Reservar turno</button>
              </div>
            </section>
          )}


          {isReservationFlow ? (
            <section className="flow-overview" aria-label={`Paso ${currentReservationStep} de 5`}>
              <button className="flow-home" onClick={resetClient}>← Volver al inicio</button>
              <div className="flow-progress-head">
                <span>Paso {currentReservationStep} de 5</span>
              </div>
              <div className="flow-progress-track" aria-hidden="true">
                <span style={{ width: reservationProgress }} />
              </div>
            </section>
          ) : null}

          {step === "barber" && (
            <section className="panel">
              <div className="step-head"><p className="eyebrow">Paso 1</p><h2>Elegí tu peluquero</h2></div>
              <div className="barber-grid">
                {barbers.map((barber) => (
                  <article key={barber.id} className={`barber-card ${Number(barberId) === barber.id ? "selected" : ""}`}>
                    <BarberAvatar barber={barber} size="lg" />
                    <div>
                      <strong>{barber.name}</strong>
                      <span>{barber.description}</span>
                    </div>
                    <button className="primary" onClick={() => { setServices([]); setBarberId(barber.id); setServiceId(null); setDate(null); setTime(null); resetAvailabilityState(); setStep("service"); }}>Elegir</button>
                  </article>
                ))}
                <article className={`barber-card ${barberId === ANY_BARBER ? "selected" : ""}`}>
                  <span className="any-avatar lg">SP</span>
                  <div>
                    <strong>Sin preferencia</strong>
                    <span>Asignamos automáticamente un peluquero disponible.</span>
                  </div>
                  <button className="primary" onClick={() => { setServices([]); setBarberId(ANY_BARBER); setServiceId(null); setDate(null); setTime(null); resetAvailabilityState(); setStep("service"); }}>Elegir</button>
                </article>
              </div>
            </section>
          )}

          {step === "service" && (
            <section className="panel">
              <div className="step-head"><p className="eyebrow">Paso 2</p><h2>Elegí el servicio</h2><p>Peluquero: <strong>{currentBarberName}</strong></p></div>
              {barberId === ANY_BARBER ? <p className="field-help">El precio final depende del profesional asignado.</p> : null}
              <div className="service-grid">
                {services.length ? services.map((service) => (
                  <button key={service.service_id || service.id} className={`service-card ${serviceId === service.id ? "selected" : ""}`} onClick={() => { setServiceId(service.id); setDate(null); setTime(null); resetAvailabilityState(); setStep("date"); }}>
                    <strong>{service.name}</strong>
                    <div className="service-meta">{serviceMetaLabel(service)}</div>
                  </button>
                )) : <p className="availability-state">Cargando servicios...</p>}
              </div>
              <div className="step-actions single">
                <button className="ghost" onClick={goBackToBarber}>← Volver</button>
              </div>
            </section>
          )}

          {step === "date" && (
            <section className="panel">
              <div className="step-head">
                <p className="eyebrow">Paso 3</p><h2>Seleccioná una fecha</h2>
                <p>Solo martes a sábado. No se permiten fechas pasadas.</p>
              </div>
              <div className="date-grid">
                {dateOptions().map((iso) => {
                  const local = parseLocalDate(iso);
                  return (
                    <button key={iso} className={`date-card ${date === iso ? "selected" : ""}`} disabled={!isOpenDay(iso)} onClick={() => { setDate(iso); setTime(null); resetAvailabilityState(true); setStep("time"); }}>
                      <span>{new Intl.DateTimeFormat("es-AR", { weekday: "short" }).format(local)}</span>
                      <strong>{local.getDate()}</strong>
                      <span>{new Intl.DateTimeFormat("es-AR", { month: "short" }).format(local)}</span>
                    </button>
                  );
                })}
              </div>
              <div className="step-actions single">
                <button className="ghost" onClick={goBackToService}>← Volver</button>
              </div>
            </section>
          )}

          {step === "time" && (
            <section className="panel">
              <div className="availability-header">
                <div><p className="eyebrow">TURNOS DISPONIBLES</p><h2>{formatDate(date)}</h2><p>Peluquero: <strong>{currentBarberName}</strong></p></div>
                <button className="ghost" onClick={goBackToDate}>← Volver</button>
              </div>
              {loadingAvailability ? (
                <p className="availability-state">Cargando horarios...</p>
              ) : availabilityError ? (
                <div className="availability-state availability-error">
                  <p>{availabilityError}</p>
                  <button className="ghost" onClick={() => { setLoadingAvailability(true); setAvailabilityKey(""); setAvailabilityRetry((value) => value + 1); }}>Reintentar</button>
                </div>
              ) : visibleAvailable.length ? (
                <div className="time-grid">
                  {visibleAvailable.map((slot) => <button key={slot} className="time-button" onClick={() => { setTime(slot); setStep("details"); }}>{timeLabel(slot)}</button>)}
                </div>
              ) : <p className="empty">No hay horarios disponibles para esta fecha.</p>}
            </section>
          )}

          {step === "details" && (
            <section className="panel">
              <div className="step-head"><p className="eyebrow">Paso 5</p><h2>Tus datos</h2></div>
              <form className="form-grid" onSubmit={submitBooking}>
                <label>Nombre<input required value={client.first_name} onChange={(e) => setClient({ ...client, first_name: e.target.value })} /></label>
                <label>Apellido<input required value={client.last_name} onChange={(e) => setClient({ ...client, last_name: e.target.value })} /></label>
                <label>Teléfono o WhatsApp
                  <input required inputMode="tel" placeholder="Ej: 3575406316" value={client.phone} aria-invalid={Boolean(phoneError)} onChange={(e) => setClient({ ...client, phone: e.target.value })} />
                  <span className={phoneError ? "field-error" : "field-help"}>{phoneError || "Ingresá código de área y número."}</span>
                </label>
                <Summary barber={currentBarberName} service={selectedService} date={date} time={time} customer={`${client.first_name} ${client.last_name}`.trim()} />
                {selectedService?.requires_deposit ? (
                  <div className="deposit-preview">
                    <strong>Este turno requiere seña</strong>
                    <span>Precio: {formatServicePrice(selectedService)}</span>
                    <span>Seña para reservar: {selectedDepositSummary?.depositLabel}</span>
                    <span>Saldo a abonar en el salón: {selectedDepositSummary?.balanceLabel}</span>
                    <p>Tu turno quedará reservado durante 10 minutos mientras realizás el pago.</p>
                  </div>
                ) : null}
                {barberId === ANY_BARBER ? <p className="field-help">El precio final depende del profesional asignado y se confirma al guardar el turno.</p> : null}
                <div className="step-actions">
                  <button className="ghost" type="button" onClick={goBackToTime}>← Volver</button>
                  <button className="primary" type="submit" disabled={bookingPending || Boolean(phoneError)}>{bookingPending ? "Procesando..." : selectedService?.requires_deposit ? "Continuar al pago" : "Confirmar turno"}</button>
                </div>
              </form>
            </section>
          )}

        </main>
      ) : (
        <main>
          {!token ? (
            <section className="admin-login panel">
              <div><p className="eyebrow">Panel privado</p><h2>Ingresar como peluquero</h2><p>Usuario demo: <strong>admin</strong></p></div>
              <form className="form-grid compact" onSubmit={submitLogin}>
                <label>Usuario<input required value={login.username} onChange={(e) => setLogin({ ...login, username: e.target.value })} /></label>
                <label>Contraseña<input required type="password" value={login.password} onChange={(e) => setLogin({ ...login, password: e.target.value })} /></label>
                <button className="primary" type="submit">Iniciar sesión</button>
              </form>
            </section>
          ) : (
            <section className="admin-panel">
              <div className="admin-toolbar">
                <div>
                  <p className="eyebrow">Panel privado</p>
                  <h2>
                    {adminSection === "agenda" ? `Agenda - ${formatDate(adminDate)}` : null}
                    {adminSection === "services" ? "Servicios" : null}
                    {adminSection === "barberServices" ? "Profesionales y servicios" : null}
                  </h2>
                  {adminSection === "services" ? <p className="admin-subtitle">Gestioná el catálogo de servicios del salón.</p> : null}
                  {adminSection === "barberServices" ? <p className="admin-subtitle">Definí qué ofrece cada profesional, con precio y duración propios.</p> : null}
                </div>
                <div className="toolbar-actions">
                  {adminSection === "agenda" ? <input type="date" value={adminDate} onChange={(e) => setAdminDate(e.target.value)} /> : null}
                  <button className="ghost" onClick={() => { localStorage.removeItem("adminToken"); setToken(""); }}>Salir</button>
                </div>
              </div>
              <div className="admin-section-tabs" role="tablist" aria-label="Panel administrador">
                <button className={`admin-section-tab ${adminSection === "agenda" ? "active" : ""}`} onClick={() => setAdminSection("agenda")}>Agenda</button>
                <button className={`admin-section-tab ${adminSection === "services" ? "active" : ""}`} onClick={() => setAdminSection("services")}>Servicios</button>
                <button className={`admin-section-tab ${adminSection === "barberServices" ? "active" : ""}`} onClick={() => setAdminSection("barberServices")}>Profesionales y servicios</button>
              </div>

              {adminSection === "agenda" ? (
                <>
                  <div className="stats">
                    <span><strong>{stats.free}</strong> libres</span>
                    <span><strong>{stats.booked}</strong> reservados</span>
                    <span><strong>{stats.blocked}</strong> bloqueados</span>
                  </div>
                  <div className="admin-tabs" role="tablist" aria-label="Peluqueros">
                    {barbers.map((barber) => (
                      <button key={barber.id} className={`admin-tab ${adminBarberTab === String(barber.id) ? "active" : ""}`} onClick={() => setAdminBarberTab(String(barber.id))}>
                        <BarberAvatar barber={barber} />
                        <span>{barber.name}</span>
                      </button>
                    ))}
                    <button className={`admin-tab ${adminBarberTab === ALL_BARBERS ? "active" : ""}`} onClick={() => setAdminBarberTab(ALL_BARBERS)}>
                      <span className="any-avatar sm">T</span>
                      <span>Todos</span>
                    </button>
                  </div>
                  {adminBarberTab === ALL_BARBERS ? (
                    <div className="agenda-groups">
                      {groupedAgenda.map(({ barber, slots }) => (
                        <section key={barber.id} className="agenda-group">
                          <h3><BarberLabel barber={barber} /></h3>
                          <div className="agenda-wrap">
                            <div className="agenda-head"><span>Hora</span><span>Fin</span><span>Peluquero</span><span>Cliente</span><span>Servicio</span><span>Estado</span><span>Acciones</span></div>
                            <div className="agenda-rows">{renderAgendaRows(slots)}</div>
                          </div>
                        </section>
                      ))}
                    </div>
                  ) : (
                    <div className="agenda-wrap">
                      <div className="agenda-head"><span>Hora</span><span>Fin</span><span>Peluquero</span><span>Cliente</span><span>Servicio</span><span>Estado</span><span>Acciones</span></div>
                      <div className="agenda-rows">{renderAgendaRows(visibleAgenda)}</div>
                    </div>
                  )}
                </>
              ) : adminSection === "services" ? (
                <div className="services-admin">
                  {serviceMessage ? (
                    <div className="admin-success" role="status">
                      <span>{serviceMessage}</span>
                      <button type="button" onClick={() => setServiceMessage("")} aria-label="Cerrar mensaje">×</button>
                    </div>
                  ) : null}
                  <div className="services-toolbar">
                    <label className="control-field">Buscar<input type="search" placeholder="Ej: Corte, Alisado..." value={serviceSearch} onChange={(e) => setServiceSearch(e.target.value)} /></label>
                    <label className="control-field">Estado<select value={serviceFilter} onChange={(e) => setServiceFilter(e.target.value)}>
                      {Object.entries(SERVICE_FILTERS).map(([value, label]) => <option key={value} value={value}>{label}</option>)}
                    </select></label>
                    <button className="primary new-service-button" onClick={openNewServiceForm}>Nuevo servicio</button>
                  </div>
                  <div className="services-list">
                    {visibleAdminServices.map((service) => (
                      <article key={service.id} className={`admin-service-card ${service.active ? "" : "inactive"}`}>
                        <div className="admin-service-main">
                          <div className="admin-service-title">
                            <strong>{service.name}</strong>
                            <span className="service-status-pill">{service.active ? "Activo" : "Inactivo"}</span>
                          </div>
                          <span className="service-category">{service.category || "Sin categoría"}</span>
                          <p className="service-description">{service.description || "Sin descripción."}</p>
                          <div className="assigned-barbers">
                            <span>{service.assigned_barbers_count === 1 ? "Profesional:" : service.assigned_barbers_count ? "Profesionales:" : "Sin profesionales asignados."}</span>
                            {service.assigned_barbers?.length ? (
                              <div className="assigned-barber-list">
                                {service.assigned_barbers.map((name) => <span key={name} className="mini-badge">{displayBarberName(name)}</span>)}
                              </div>
                            ) : null}
                          </div>
                        </div>
                        <div className="service-admin-meta">
                          <span>{pluralize(service.assigned_barbers_count, "profesional activo", "profesionales activos")}</span>
                          <span>{pluralize(service.future_appointments_count || 0, "turno futuro", "turnos futuros")}</span>
                        </div>
                        <div className="row-actions">
                          <button className="configure-action" onClick={() => loadQuickServiceConfig(service)}>Configurar</button>
                          <button className="edit-action" onClick={() => openEditServiceForm(service)}>Editar</button>
                          <button className={service.active ? "warning-action" : "reactivate-action"} onClick={() => setServiceConfirm(service)}>{service.active ? "Desactivar" : "Reactivar"}</button>
                        </div>
                      </article>
                    ))}
                    {!visibleAdminServices.length ? (
                      <div className="services-empty">
                        <strong>{adminServices.length ? "No encontramos servicios con esos filtros." : "Aún no hay servicios."}</strong>
                        <span>{adminServices.length ? "Probá cambiar la búsqueda o el estado seleccionado." : "Creá el primero para comenzar a configurar el salón."}</span>
                        {!adminServices.length ? <button className="primary" onClick={openNewServiceForm}>Nuevo servicio</button> : null}
                      </div>
                    ) : null}
                  </div>
                </div>
              ) : (
                <div className="services-admin barber-services-admin">
                  {barberServiceMessage ? (
                    <div className="admin-success" role="status">
                      <span>{barberServiceMessage}</span>
                      <button type="button" onClick={() => setBarberServiceMessage("")} aria-label="Cerrar mensaje">×</button>
                    </div>
                  ) : null}
                  <div className="admin-tabs config-barber-tabs" role="tablist" aria-label="Profesionales">
                    {barbers.map((barber) => (
                      <button key={barber.id} className={`admin-tab ${String(configBarberId) === String(barber.id) ? "active" : ""}`} onClick={() => setConfigBarberId(String(barber.id))}>
                        <BarberAvatar barber={barber} />
                        <span>{barber.name}</span>
                      </button>
                    ))}
                  </div>
                  <div className="services-toolbar config-toolbar">
                    <div>
                      <p className="eyebrow">Configuración</p>
                      <strong>{selectedConfigBarber ? displayBarberName(selectedConfigBarber.name) : "Seleccioná un profesional"}</strong>
                    </div>
                    <label className="control-field">Buscar servicio<input type="search" placeholder="Ej: Corte, Alisado..." value={barberServiceSearch} onChange={(e) => setBarberServiceSearch(e.target.value)} /></label>
                  </div>
                  <div className="services-list">
                    {visibleBarberServiceConfigs.map((item) => (
                      <article key={item.service_id} className={`admin-service-card barber-service-card ${!item.service_active || (item.assigned && !item.active) ? "inactive" : ""}`}>
                        <div className="admin-service-main">
                          <div className="admin-service-title">
                            <strong>{item.service_name}</strong>
                            <span className={`service-status-pill ${item.assigned ? "" : "neutral"}`}>{item.assigned ? item.active ? "Asignado activo" : "Asignado inactivo" : "No asignado"}</span>
                            {!item.service_active ? <span className="service-status-pill muted">Servicio global inactivo</span> : null}
                          </div>
                          <span className="service-category">{item.service_category || "Sin categoría"}</span>
                          <p className="service-description">{item.service_description || "Sin descripción."}</p>
                        </div>
                        <div className="service-admin-meta config-meta">
                          <span>{formatPrice(item.price)} · {formatDuration(item.duration_visible_minutes)}</span>
                          <span>Bloqueo {formatAdminMinutes(item.blocking_duration_minutes)}</span>
                        </div>
                        <div className="row-actions">
                          <button className="edit-action" onClick={() => openBarberServiceForm(item)}>{item.assigned ? "Editar" : "Asignar"}</button>
                          {item.assigned ? (
                            <button className={item.active ? "warning-action" : "reactivate-action"} onClick={() => setBarberServiceConfirm(item)}>{item.active ? "Desactivar" : "Reactivar"}</button>
                          ) : null}
                        </div>
                      </article>
                    ))}
                    {!visibleBarberServiceConfigs.length ? (
                      <div className="services-empty">
                        <strong>No encontramos servicios con esa búsqueda.</strong>
                        <span>Probá cambiar el texto o revisar el catálogo global.</span>
                      </div>
                    ) : null}
                  </div>
                </div>
              )}
            </section>
          )}
        </main>
      )}


      {view === "client" && step === "confirmation" && booking ? (
        <div className="modal-layer confirmation-modal" role="presentation">
          <section className="dialog-card confirmed-dialog" role="dialog" aria-modal="true" aria-labelledby="confirmed-title" tabIndex="-1" ref={confirmationDialogRef}>
            <button className="dialog-close" type="button" onClick={closeConfirmationModal} aria-label="Cerrar">Cerrar</button>
            <div className="success-mark">{booking.creation_status === "PENDING_PAYMENT" ? "10" : "OK"}</div>
            <p className="eyebrow">{booking.creation_status === "PENDING_PAYMENT" ? "Pendiente de pago" : "Turno confirmado"}</p>
            <h2 id="confirmed-title">{booking.creation_status === "PENDING_PAYMENT" ? "Turno retenido" : "Turno confirmado"}</h2>
            <p className="modal-lead">
              {booking.creation_status === "PENDING_PAYMENT"
                ? "El horario quedó retenido temporalmente mientras se completa el pago de la seña."
                : "Tu turno fue reservado correctamente."}
            </p>
            <Summary
              barber={booking.barber_name}
              service={{
                name: booking.service_name,
                price: booking.service_price,
                duration_visible_minutes: booking.service_visible_duration_minutes,
              }}
              date={booking.date}
              time={booking.start_time}
              customer={`${booking.client_first_name} ${booking.client_last_name}`}
              phone={booking.client_phone}
            />
            {booking.deposit_amount !== null && booking.deposit_amount !== undefined ? (
              <div className="deposit-preview confirmed-deposit">
                <span>Seña para reservar: {formatPrice(booking.deposit_amount)}</span>
                <span>Saldo a abonar en el salón: {formatPrice(booking.remaining_balance)}</span>
                {booking.payment_expires_at ? <p>Vence: {new Date(booking.payment_expires_at).toLocaleString("es-AR")}</p> : null}
              </div>
            ) : null}
            {booking.creation_status === "PENDING_PAYMENT" ? (
              <div className="cancel-link-box highlighted">
                <p>Tu horario está retenido durante {booking.payment_expires_at ? "unos minutos" : "el tiempo indicado"}.</p>
                <span>Seña: {formatPrice(booking.deposit_amount)}</span>
                {booking.payment_expires_at ? <span className="cancel-url">Vence: {new Date(booking.payment_expires_at).toLocaleString("es-AR")}</span> : null}
                <div className="modal-actions">
                  <button className="primary" type="button" disabled={!booking.checkout_url && !booking.payment_status_token} onClick={openMercadoPagoCheckout}>Pagar seña con Mercado Pago</button>
                  <button className="ghost" type="button" onClick={closeConfirmationModal}>Cerrar</button>
                </div>
              </div>
            ) : (
              <>
                <div className="cancel-link-box highlighted">
                  <p>Guardá tu enlace de cancelación.<br />También podés enviártelo por WhatsApp usando el botón de abajo.</p>
                  <span className="cancel-url">{bookingCancellationLink(booking)}</span>
                </div>
                <div className="modal-actions">
                  <button className="primary whatsapp-button" type="button" onClick={openWhatsAppConfirmation}>Enviar registro de turno por Whatsapp</button>
                  <button className="ghost" type="button" onClick={copyCancellationLink}>Copiar enlace de cancelación</button>
                </div>
              </>
            )}
            {copyMessage ? <span className="copy-message">{copyMessage}</span> : null}
          </section>
        </div>
      ) : null}

      {serviceForm ? (
        <div className="modal-layer">
          <form className="dialog-card service-dialog" onSubmit={submitServiceForm}>
            <div>
              <p className="eyebrow">{serviceForm.mode === "edit" ? "Editar servicio" : "Nuevo servicio"}</p>
              <h3>{serviceForm.mode === "edit" ? serviceForm.name : "Crear servicio"}</h3>
            </div>
            <label>Nombre<input required maxLength="120" value={serviceForm.name} onChange={(e) => setServiceForm({ ...serviceForm, name: e.target.value })} /><span className="field-help">Usá un nombre claro, por ejemplo “Alisado”.</span></label>
            <label>Descripción<input maxLength="255" value={serviceForm.description} onChange={(e) => setServiceForm({ ...serviceForm, description: e.target.value })} /><span className="field-help">Opcional. Ayuda a identificar el servicio dentro del panel.</span></label>
            <label>Categoría<input maxLength="80" value={serviceForm.category} onChange={(e) => setServiceForm({ ...serviceForm, category: e.target.value })} /><span className="field-help">Opcional. Ejemplo: Cortes, Tratamientos, Barba.</span></label>
            <label className="toggle-row">
              <input type="checkbox" checked={serviceForm.active} onChange={(e) => setServiceForm({ ...serviceForm, active: e.target.checked })} />
              <span>Servicio activo</span>
            </label>
            <p className="field-help">El precio, la duración y los profesionales asignados se configuran por peluquero en otra sección.</p>
            <menu>
              <button type="button" className="ghost" disabled={serviceSaving} onClick={() => setServiceForm(null)}>Cancelar</button>
              <button className="primary" type="submit" disabled={serviceSaving}>{serviceSaving ? "Guardando..." : "Guardar"}</button>
            </menu>
          </form>
        </div>
      ) : null}

      {serviceConfirm ? (
        <div className="modal-layer">
          <section className="dialog-card service-dialog">
            <div>
              <p className="eyebrow">{serviceConfirm.active ? "Desactivar servicio" : "Activar servicio"}</p>
              <h3>{serviceConfirm.name}</h3>
            </div>
            {serviceConfirm.active ? (
              <p>Este servicio dejará de estar disponible para nuevas reservas. Los turnos existentes no se modificarán.</p>
            ) : (
              <p>El servicio volverá a estar disponible solo si está asignado a un profesional activo.</p>
            )}
            {serviceConfirm.future_appointments_count ? <p className="field-help">Tiene {serviceConfirm.future_appointments_count} turnos futuros. No se cancelarán automáticamente.</p> : null}
            <menu>
              <button type="button" className="ghost" disabled={serviceSaving} onClick={() => setServiceConfirm(null)}>Volver</button>
              <button className="primary" type="button" disabled={serviceSaving} onClick={confirmServiceStatusChange}>{serviceSaving ? "Guardando..." : serviceConfirm.active ? "Desactivar" : "Activar"}</button>
            </menu>
          </section>
        </div>
      ) : null}

      {quickServiceConfig ? (
        <div className="modal-layer">
          <section className="dialog-card service-dialog quick-config-dialog">
            <div>
              <p className="eyebrow">Configurar servicio</p>
              <h3>{quickServiceConfig.name}</h3>
              <p>Asigná profesionales y ajustá precio, duración visible y bloqueo de agenda.</p>
            </div>
            {barberServiceMessage ? (
              <div className="admin-success" role="status">
                <span>{barberServiceMessage}</span>
                <button type="button" onClick={() => setBarberServiceMessage("")} aria-label="Cerrar mensaje">×</button>
              </div>
            ) : null}
            {quickConfigLoading ? (
              <div className="services-empty compact-empty"><span>Cargando configuración...</span></div>
            ) : (
              <div className="quick-config-list">
                {quickServiceItems.map((item) => (
                  <article key={item.barber_id} className="quick-config-row">
                    <div>
                      <strong>{displayBarberName(item.barber_name)}</strong>
                      <span className={`mini-status ${item.assigned && item.active ? "active" : ""}`}>{item.assigned && item.active ? "Lo ofrece" : "No lo ofrece"}</span>
                    </div>
                    <div className="quick-config-meta">
                      {item.assigned ? (
                        <>
                          <span>{formatPrice(item.price)}</span>
                          <span>{formatDuration(item.duration_visible_minutes)}</span>
                          <span>Bloqueo {formatAdminMinutes(item.blocking_duration_minutes)}</span>
                        </>
                      ) : (
                        <span>Sin configurar</span>
                      )}
                    </div>
                    <div className="row-actions">
                      <button className={item.assigned ? "edit-action" : "configure-action"} onClick={() => openBarberServiceForm(item)}>{item.assigned ? "Editar" : "Asignar"}</button>
                      {item.assigned ? (
                        <button className={item.active ? "warning-action" : "reactivate-action"} onClick={() => setBarberServiceConfirm(item)}>{item.active ? "Desactivar" : "Reactivar"}</button>
                      ) : null}
                    </div>
                  </article>
                ))}
              </div>
            )}
            <menu>
              <button type="button" className="ghost" disabled={barberServiceSaving} onClick={() => { setQuickServiceConfig(null); setQuickServiceItems([]); }}>Cerrar</button>
            </menu>
          </section>
        </div>
      ) : null}

      {barberServiceForm ? (
        <div className="modal-layer">
          <form className="dialog-card service-dialog config-dialog" onSubmit={submitBarberServiceForm}>
            <div>
              <p className="eyebrow">{barberServiceForm.mode === "assign" ? "Asignar servicio" : "Editar configuración"}</p>
              <h3>{barberServiceForm.service_name}</h3>
              <p>{barberServiceForm.barber_name || selectedConfigBarber ? displayBarberName(barberServiceForm.barber_name || selectedConfigBarber.name) : "Profesional seleccionado"}</p>
            </div>
            <label className="toggle-row">
              <input type="checkbox" checked={barberServiceForm.priceConsultation} onChange={(e) => setBarberServiceForm({ ...barberServiceForm, priceConsultation: e.target.checked, price: e.target.checked ? "" : barberServiceForm.price })} />
              <span>Precio a consultar</span>
            </label>
            {!barberServiceForm.priceConsultation ? (
              <label>Precio
                <input required type="number" min="0" step="0.01" value={barberServiceForm.price} onChange={(e) => setBarberServiceForm({ ...barberServiceForm, price: e.target.value })} />
                <span className="field-help">Usá pesos argentinos. Ejemplo: 18000.</span>
              </label>
            ) : null}
            <label className="toggle-row">
              <input type="checkbox" checked={barberServiceForm.durationConsultation} onChange={(e) => setBarberServiceForm({ ...barberServiceForm, durationConsultation: e.target.checked, duration_visible_minutes: e.target.checked ? "" : barberServiceForm.duration_visible_minutes })} />
              <span>Duración visible a consultar</span>
            </label>
            {!barberServiceForm.durationConsultation ? (
              <label>Tiempo visible para el cliente
                <input required type="number" min="1" step="1" value={barberServiceForm.duration_visible_minutes} onChange={(e) => setBarberServiceForm({ ...barberServiceForm, duration_visible_minutes: e.target.value })} />
                <span className="field-help">Es informativa para cliente y WhatsApp.</span>
              </label>
            ) : null}
            <label>Tiempo de bloqueo en tu agenda.
              <input required type="number" min="1" step="1" value={barberServiceForm.blocking_duration_minutes} onChange={(e) => setBarberServiceForm({ ...barberServiceForm, blocking_duration_minutes: e.target.value })} />
              <span className="field-help">Es el tiempo real que ocupa en la agenda del profesional.</span>
            </label>
            <label className="toggle-row">
              <input type="checkbox" checked={barberServiceForm.active} onChange={(e) => setBarberServiceForm({ ...barberServiceForm, active: e.target.checked })} />
              <span>Disponible para reservas nuevas con este profesional</span>
            </label>
            <menu>
              <button type="button" className="ghost" disabled={barberServiceSaving} onClick={() => setBarberServiceForm(null)}>Cancelar</button>
              <button className="primary" type="submit" disabled={barberServiceSaving}>{barberServiceSaving ? "Guardando..." : "Guardar"}</button>
            </menu>
          </form>
        </div>
      ) : null}

      {barberServiceConfirm ? (
        <div className="modal-layer">
          <section className="dialog-card service-dialog">
            <div>
              <p className="eyebrow">{barberServiceConfirm.active ? "Desactivar para profesional" : "Reactivar para profesional"}</p>
              <h3>{barberServiceConfirm.service_name}</h3>
            </div>
            {barberServiceConfirm.active ? (
              <p>Este servicio dejará de aparecer en nuevas reservas para {selectedConfigBarber ? displayBarberName(selectedConfigBarber.name) : "este profesional"}. Los turnos existentes no se modifican.</p>
            ) : (
              <p>El servicio volverá a estar disponible para nuevas reservas con este profesional si el servicio global también está activo.</p>
            )}
            <menu>
              <button type="button" className="ghost" disabled={barberServiceSaving} onClick={() => setBarberServiceConfirm(null)}>Volver</button>
              <button className="primary" type="button" disabled={barberServiceSaving} onClick={confirmBarberServiceStatusChange}>{barberServiceSaving ? "Guardando..." : barberServiceConfirm.active ? "Desactivar" : "Reactivar"}</button>
            </menu>
          </section>
        </div>
      ) : null}

      {manual ? (
        <div className="modal-layer">
          <form className="dialog-card" onSubmit={submitManual}>
            <div><p className="eyebrow">Registrar turno manual</p><h3>{formatDate(adminDate)} · {timeLabel(manual.time)}</h3></div>
            <label>Peluquero<select value={manual.barber_id} onChange={(e) => setManual({ ...manual, barber_id: e.target.value, service_id: "" })}>{barbers.map((barber) => <option key={barber.id} value={barber.id}>{barber.name}</option>)}</select></label>
            <label>Nombre<input required value={manual.first_name} onChange={(e) => setManual({ ...manual, first_name: e.target.value })} /></label>
            <label>Apellido<input value={manual.last_name} onChange={(e) => setManual({ ...manual, last_name: e.target.value })} /></label>
            <label>Teléfono <span>opcional</span><input value={manual.phone} onChange={(e) => setManual({ ...manual, phone: e.target.value })} /></label>
            <label>Servicio<select required value={manual.service_id} onChange={(e) => setManual({ ...manual, service_id: e.target.value })}>{manualServices.map((service) => <option key={service.id} value={service.id}>{service.name} · {formatServicePrice(service)} · {formatServiceDuration(service)}</option>)}</select></label>
            <menu><button type="button" className="ghost" onClick={() => setManual(null)}>Cerrar</button><button className="primary" type="submit">Guardar</button></menu>
          </form>
        </div>
      ) : null}
    </div>
  );
}
