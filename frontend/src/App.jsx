import { useEffect, useMemo, useRef, useState } from "react";
import React from "react";
import { api } from "./api";

const TZ = "America/Argentina/Cordoba";
const MIN_BOOKING_NOTICE_MINUTES = 20;
const ANY_BARBER = "any";
const ALL_BARBERS = "all";
const BUSINESS_NAME = "Marcelo Navarro";
const RESERVATION_STEPS = ["barber", "service", "date", "time", "details"];

const BARBER_VISUALS = {
  marcelo: {
    name: "Marcelo Navarro",
    description: "Cortes clásicos, barba y atención unisex.",
    photo_url: "/barbers/marcelo.jpeg",
  },
  jeremias: {
    name: "Jeremías Vivas",
    description: "Atención unisex, cortes actuales y turnos de apoyo.",
    photo_url: "/barbers/jeremias.jpeg",
  },
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
    `Peluquero: ${normalizeBarberName(booking.barber_name)}`,
    `Servicio: ${booking.service_name}`,
    `Fecha: ${formatDate(booking.date)}`,
    `Hora: ${timeLabel(booking.start_time)}`,
    "",
    "Para cancelar tu turno:",
    link,
  ].join("\n");
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

function normalizeBarber(barber) {
  const originalName = barber?.name || barber?.barber_name || "";
  const isJeremias = Number(barber?.id || barber?.barber_id) === 2 || originalName.includes("Equipo") || originalName.includes("Jerem");
  const visual = isJeremias ? BARBER_VISUALS.jeremias : BARBER_VISUALS.marcelo;
  return {
    ...barber,
    name: visual.name,
    barber_name: visual.name,
    description: visual.description,
    photo_url: visual.photo_url,
  };
}

function normalizeBarberName(name) {
  if (!name) return "-";
  if (name.includes("Equipo") || name.includes("Jerem")) return BARBER_VISUALS.jeremias.name;
  return BARBER_VISUALS.marcelo.name;
}

function barberById(barbers, barberId) {
  return barbers.find((item) => item.id === Number(barberId));
}

function selectedBarberName(barbers, barberId) {
  if (barberId === ANY_BARBER) return "Sin preferencia";
  return barberById(barbers, barberId)?.name || "-";
}

function reservationStepNumber(step) {
  const index = RESERVATION_STEPS.indexOf(step);
  return index >= 0 ? index + 1 : 0;
}

function BarberAvatar({ barber, name, size = "sm" }) {
  const displayName = barber?.name || normalizeBarberName(name);
  const photoUrl = barber?.photo_url || (displayName.includes("Jerem") ? BARBER_VISUALS.jeremias.photo_url : BARBER_VISUALS.marcelo.photo_url);
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
  const displayName = barber?.name || normalizeBarberName(name);
  return (
    <span className="barber-label">
      <BarberAvatar barber={barber} name={displayName} />
      <span>{displayName}</span>
    </span>
  );
}

function Summary({ barber, service, date, time, customer, phone }) {
  const barberName = barber ? normalizeBarberName(barber) : "";
  return (
    <div className="summary">
      {barber ? <div><span>Peluquero</span><strong><BarberLabel name={barberName} /></strong></div> : null}
      <div><span>Servicio</span><strong>{service?.name || "-"}</strong></div>
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
  const [adminDate, setAdminDate] = useState(firstOpenDate());
  const [adminBarberTab, setAdminBarberTab] = useState(null);
  const [agenda, setAgenda] = useState([]);
  const [manual, setManual] = useState(null);
  const [cancelToken] = useState(cancellationTokenFromPath());
  const [cancelAppointmentData, setCancelAppointmentData] = useState(null);
  const [cancelStatus, setCancelStatus] = useState("loading");
  const [cancelError, setCancelError] = useState("");
  const phoneError = client.phone && !isValidPhoneInput(client.phone) ? "Ingresá un teléfono válido de 10 u 11 números." : "";
  const selectedService = services.find((item) => item.id === Number(serviceId));
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
  const isReservationFlow = view === "client" && RESERVATION_STEPS.includes(step);
  const currentReservationStep = reservationStepNumber(step);
  const reservationProgress = currentReservationStep ? `${currentReservationStep * 20}%` : "0%";

  useEffect(() => {
    api.services().then(setServices).catch((err) => setError(err.message));
    api.barbers().then((items) => setBarbers(items.map(normalizeBarber))).catch((err) => setError(err.message));
  }, []);

  useEffect(() => {
    if (!adminBarberTab && barbers.length) setAdminBarberTab(String(barbers[0].id));
  }, [adminBarberTab, barbers]);

  useEffect(() => {
    if (!cancelToken) return;
    api.cancellationDetails(cancelToken)
      .then((data) => {
        setCancelAppointmentData({ ...data, barber_name: normalizeBarberName(data.barber_name) });
        setCancelStatus("ready");
        setCancelError("");
      })
      .catch((err) => {
        setCancelStatus("error");
        setCancelError(err.message);
      });
  }, [cancelToken]);

  useEffect(() => {
    if (step === "time" && date) {
      const queryBarber = barberId === ANY_BARBER ? null : barberId;
      const nextAvailabilityKey = `${date}:${queryBarber || ANY_BARBER}`;
      if (availabilityKey === nextAvailabilityKey) return;
      const requestKey = `${nextAvailabilityKey}:${availabilityRetry}`;
      availabilityRequestRef.current = requestKey;
      setLoadingAvailability(true);
      setAvailabilityError("");
      api.availability(date, queryBarber)
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
  }, [step, date, barberId, availabilityKey, availabilityRetry]);

  useEffect(() => {
    if (view === "admin" && token) refreshAgenda();
  }, [view, token, adminDate]);

  const stats = useMemo(() => ({
    free: visibleAgenda.filter((slot) => slot.status === "Libre").length,
    booked: visibleAgenda.filter((slot) => slot.status === "Reservado").length,
    blocked: visibleAgenda.filter((slot) => slot.status === "Bloqueado").length,
  }), [visibleAgenda]);

  async function refreshAgenda() {
    try {
      setAgenda((await api.agenda(adminDate)).map((slot) => ({
        ...slot,
        barber_name: normalizeBarberName(slot.barber_name),
        appointment: slot.appointment ? { ...slot.appointment, barber_name: normalizeBarberName(slot.appointment.barber_name) } : slot.appointment,
      })));
    } catch (err) {
      setError(err.message);
    }
  }

  function showCopyFeedback(message) {
    setCopyMessage(message);
    window.setTimeout(() => setCopyMessage(""), 2500);
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
      setBooking({ ...saved, barber_name: normalizeBarberName(saved.barber_name) });
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
          <span><BarberLabel barber={barber} name={slot.barber_name} /></span>
          <span>{slot.appointment ? `${slot.appointment.client_first_name} ${slot.appointment.client_last_name}` : slot.status === "Bloqueado" ? "Horario bloqueado" : "Disponible"}</span>
          <span>{slot.appointment?.service_name || "-"}</span>
          <span className={`status ${slot.status === "Libre" ? "free" : slot.status === "Bloqueado" ? "blocked" : "booked"}`}>{slot.appointment?.origin === "MANUAL" ? "Registrado manualmente" : slot.status}</span>
          <div className="row-actions">
            {slot.status === "Libre" && <><button onClick={() => setManual({ time: slot.time, barber_id: slot.barber_id, service_id: services[0]?.id || "", first_name: "", last_name: "", phone: "" })}>Registrar</button><button onClick={() => blockSlot(slot)}>Bloquear</button></>}
            {slot.status === "Reservado" && <button onClick={() => cancelAppointment(slot)}>Cancelar</button>}
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
                  service={{ name: cancelAppointmentData.service_name }}
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
                    <button className="primary" onClick={() => { setBarberId(barber.id); setServiceId(null); setDate(null); setTime(null); resetAvailabilityState(); setStep("service"); }}>Elegir</button>
                  </article>
                ))}
                <article className={`barber-card ${barberId === ANY_BARBER ? "selected" : ""}`}>
                  <span className="any-avatar lg">SP</span>
                  <div>
                    <strong>Sin preferencia</strong>
                    <span>Asignamos automáticamente un peluquero disponible.</span>
                  </div>
                  <button className="primary" onClick={() => { setBarberId(ANY_BARBER); setServiceId(null); setDate(null); setTime(null); resetAvailabilityState(); setStep("service"); }}>Elegir</button>
                </article>
              </div>
            </section>
          )}

          {step === "service" && (
            <section className="panel">
              <div className="step-head"><p className="eyebrow">Paso 2</p><h2>Elegí el servicio</h2><p>Peluquero: <strong>{currentBarberName}</strong></p></div>
              <div className="service-grid">
                {services.map((service) => (
                  <button key={service.id} className={`service-card ${serviceId === service.id ? "selected" : ""}`} onClick={() => { setServiceId(service.id); setDate(null); setTime(null); resetAvailabilityState(); setStep("date"); }}>
                    <strong>{service.name}</strong><span>{service.duration_minutes} minutos</span>
                  </button>
                ))}
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
                <div className="step-actions">
                  <button className="ghost" type="button" onClick={goBackToTime}>← Volver</button>
                  <button className="primary" type="submit" disabled={bookingPending || Boolean(phoneError)}>{bookingPending ? "Confirmando turno..." : "Confirmar turno"}</button>
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
                <div><p className="eyebrow">Agenda</p><h2>Agenda - {formatDate(adminDate)}</h2></div>
                <div className="toolbar-actions">
                  <input type="date" value={adminDate} onChange={(e) => setAdminDate(e.target.value)} />
                  <button className="ghost" onClick={() => { localStorage.removeItem("adminToken"); setToken(""); }}>Salir</button>
                </div>
              </div>
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
                        <div className="agenda-head"><span>Hora</span><span>Peluquero</span><span>Cliente</span><span>Servicio</span><span>Estado</span><span>Acciones</span></div>
                        <div className="agenda-rows">{renderAgendaRows(slots)}</div>
                      </div>
                    </section>
                  ))}
                </div>
              ) : (
                <div className="agenda-wrap">
                  <div className="agenda-head"><span>Hora</span><span>Peluquero</span><span>Cliente</span><span>Servicio</span><span>Estado</span><span>Acciones</span></div>
                  <div className="agenda-rows">{renderAgendaRows(visibleAgenda)}</div>
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
            <div className="success-mark">OK</div>
            <p className="eyebrow">Turno confirmado</p>
            <h2 id="confirmed-title">Turno confirmado</h2>
            <p className="modal-lead">Tu turno fue reservado correctamente.</p>
            <Summary
              barber={booking.barber_name}
              service={{ name: booking.service_name }}
              date={booking.date}
              time={booking.start_time}
              customer={`${booking.client_first_name} ${booking.client_last_name}`}
              phone={booking.client_phone}
            />
            <div className="cancel-link-box highlighted">
              <p>Guardá tu enlace de cancelación.<br />También podés enviártelo por WhatsApp usando el botón de abajo.</p>
              <span className="cancel-url">{bookingCancellationLink(booking)}</span>
            </div>
            <div className="modal-actions">
              <button className="primary whatsapp-button" type="button" onClick={openWhatsAppConfirmation}>Enviar registro de turno por Whatsapp</button>
              <button className="ghost" type="button" onClick={copyCancellationLink}>Copiar enlace de cancelación</button>
            </div>
            {copyMessage ? <span className="copy-message">{copyMessage}</span> : null}
          </section>
        </div>
      ) : null}

      {manual ? (
        <div className="modal-layer">
          <form className="dialog-card" onSubmit={submitManual}>
            <div><p className="eyebrow">Registrar turno manual</p><h3>{formatDate(adminDate)} · {timeLabel(manual.time)}</h3></div>
            <label>Peluquero<select value={manual.barber_id} onChange={(e) => setManual({ ...manual, barber_id: e.target.value })}>{barbers.map((barber) => <option key={barber.id} value={barber.id}>{barber.name}</option>)}</select></label>
            <label>Nombre<input required value={manual.first_name} onChange={(e) => setManual({ ...manual, first_name: e.target.value })} /></label>
            <label>Apellido<input value={manual.last_name} onChange={(e) => setManual({ ...manual, last_name: e.target.value })} /></label>
            <label>Teléfono <span>opcional</span><input value={manual.phone} onChange={(e) => setManual({ ...manual, phone: e.target.value })} /></label>
            <label>Servicio<select value={manual.service_id} onChange={(e) => setManual({ ...manual, service_id: e.target.value })}>{services.map((service) => <option key={service.id} value={service.id}>{service.name}</option>)}</select></label>
            <menu><button type="button" className="ghost" onClick={() => setManual(null)}>Cerrar</button><button className="primary" type="submit">Guardar</button></menu>
          </form>
        </div>
      ) : null}
    </div>
  );
}
