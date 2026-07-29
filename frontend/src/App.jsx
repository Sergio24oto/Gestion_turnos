import { useEffect, useMemo, useState } from "react";
import React from "react";
import { api } from "./api";

const TZ = "America/Argentina/Cordoba";
const MIN_BOOKING_NOTICE_MINUTES = 20;

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

function Summary({ service, date, time, customer }) {
  return (
    <div className="summary">
      <div><span>Servicio</span><strong>{service?.name || "-"}</strong></div>
      <div><span>Fecha</span><strong>{date ? formatDate(date) : "-"}</strong></div>
      <div><span>Hora</span><strong>{time ? timeLabel(time) : "-"}</strong></div>
      {customer ? <div><span>Cliente</span><strong>{customer}</strong></div> : null}
    </div>
  );
}

export default function App() {
  const [view, setView] = useState("client");
  const [step, setStep] = useState("welcome");
  const [services, setServices] = useState([]);
  const [serviceId, setServiceId] = useState(null);
  const [date, setDate] = useState(firstOpenDate());
  const [available, setAvailable] = useState([]);
  const [time, setTime] = useState(null);
  const [client, setClient] = useState({ first_name: "", last_name: "", phone: "" });
  const [booking, setBooking] = useState(null);
  const [copyMessage, setCopyMessage] = useState("");
  const [error, setError] = useState("");
  const [token, setToken] = useState(localStorage.getItem("adminToken") || "");
  const [login, setLogin] = useState({ username: "admin", password: "" });
  const [adminDate, setAdminDate] = useState(firstOpenDate());
  const [agenda, setAgenda] = useState([]);
  const [manual, setManual] = useState(null);
  const [cancelToken] = useState(cancellationTokenFromPath());
  const [cancelAppointmentData, setCancelAppointmentData] = useState(null);
  const [cancelStatus, setCancelStatus] = useState("loading");
  const [cancelError, setCancelError] = useState("");
  const selectedService = services.find((item) => item.id === Number(serviceId));
  const visibleAvailable = useMemo(
    () => available.filter((slot) => isBookableSlot(date, slot)),
    [available, date]
  );

  useEffect(() => {
    api.services().then(setServices).catch((err) => setError(err.message));
  }, []);

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
    if (step === "time" && date) {
      api.availability(date).then(setAvailable).catch((err) => setError(err.message));
    }
  }, [step, date]);

  useEffect(() => {
    if (view === "admin" && token) refreshAgenda();
  }, [view, token, adminDate]);

  const stats = useMemo(() => ({
    free: agenda.filter((slot) => slot.status === "Libre").length,
    booked: agenda.filter((slot) => slot.status === "Reservado").length,
    blocked: agenda.filter((slot) => slot.status === "Bloqueado").length,
  }), [agenda]);

  async function refreshAgenda() {
    try {
      setAgenda(await api.agenda(adminDate));
    } catch (err) {
      setError(err.message);
    }
  }

  async function submitBooking(event) {
    event.preventDefault();
    setError("");
    try {
      const saved = await api.createAppointment({
        service_id: Number(serviceId),
        date,
        start_time: time,
        client,
      });
      setBooking(saved);
      setCopyMessage("");
      setStep("confirmation");
    } catch (err) {
      setError(err.message);
      setStep("time");
      api.availability(date).then(setAvailable);
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

  function resetClient() {
    setStep("welcome");
    setServiceId(null);
    setTime(null);
    setClient({ first_name: "", last_name: "", phone: "" });
    setBooking(null);
    setCopyMessage("");
    setError("");
  }

  async function copyCancellationLink() {
    if (!booking?.cancellation_token) return;
    const link = cancellationLink(booking.cancellation_token);
    if (navigator.clipboard) {
      await navigator.clipboard.writeText(link);
    }
    setCopyMessage("Enlace copiado.");
  }

  function openCancellationLink() {
    if (!booking?.cancellation_token) return;
    window.open(cancellationLink(booking.cancellation_token), "_blank", "noopener,noreferrer");
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
    <div className="shell">
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

      {error ? <p className="error global-error">{error}</p> : null}

      {view === "client" ? (
        <main>
          {step === "welcome" && (
            <section className="hero active">
              <div className="hero-copy">
                <div className="logo-large"><img src="/marcelo-navarro-logo.png" alt="Marcelo Navarro Peluqueria Unisex" /></div>
                <p className="eyebrow">Agenda online</p>
                <h1>Reserva tu proximo corte sin esperar mensajes.</h1>
                <p className="lead">ElegÃ­ servicio, fecha y horario disponible. Sin cuenta y en pocos pasos.</p>
                <button className="primary cta" onClick={() => setStep("service")}>Reservar turno</button>
              </div>
              <aside className="phone-preview" aria-label="Vista previa de turnos disponibles">
                <p>TURNOS DISPONIBLES</p>
                <h2>MiÃ©rcoles 25 de septiembre</h2>
                <div className="preview-times">
                  <span>09:00 hs.</span><span>09:20 hs.</span><span>09:40 hs.</span>
                  <span>10:00 hs.</span><span>10:20 hs.</span><span>10:40 hs.</span>
                </div>
              </aside>
            </section>
          )}

          {step === "service" && (
            <section className="panel">
              <div className="step-head"><p className="eyebrow">Paso 1</p><h2>ElegÃ­ el servicio</h2></div>
              <div className="service-grid">
                {services.map((service) => (
                  <button key={service.id} className={`service-card ${serviceId === service.id ? "selected" : ""}`} onClick={() => { setServiceId(service.id); setStep("date"); }}>
                    <strong>{service.name}</strong><span>{service.duration_minutes} minutos</span>
                  </button>
                ))}
              </div>
            </section>
          )}

          {step === "date" && (
            <section className="panel">
              <div className="step-head">
                <p className="eyebrow">Paso 2</p><h2>SeleccionÃ¡ una fecha</h2>
                <p>Solo martes a sÃ¡bado. No se permiten fechas pasadas.</p>
              </div>
              <div className="date-grid">
                {dateOptions().map((iso) => {
                  const local = parseLocalDate(iso);
                  return (
                    <button key={iso} className={`date-card ${date === iso ? "selected" : ""}`} disabled={!isOpenDay(iso)} onClick={() => { setDate(iso); setStep("time"); }}>
                      <span>{new Intl.DateTimeFormat("es-AR", { weekday: "short" }).format(local)}</span>
                      <strong>{local.getDate()}</strong>
                      <span>{new Intl.DateTimeFormat("es-AR", { month: "short" }).format(local)}</span>
                    </button>
                  );
                })}
              </div>
            </section>
          )}

          {step === "time" && (
            <section className="panel">
              <div className="availability-header">
                <div><p className="eyebrow">TURNOS DISPONIBLES</p><h2>{formatDate(date)}</h2></div>
                <button className="ghost" onClick={() => setStep("date")}>Cambiar fecha</button>
              </div>
              {visibleAvailable.length ? (
                <div className="time-grid">
                  {visibleAvailable.map((slot) => <button key={slot} className="time-button" onClick={() => { setTime(slot); setStep("details"); }}>{timeLabel(slot)}</button>)}
                </div>
              ) : <p className="empty">No quedan turnos disponibles para esta fecha.</p>}
            </section>
          )}

          {step === "details" && (
            <section className="panel">
              <div className="step-head"><p className="eyebrow">Paso 4</p><h2>Tus datos</h2></div>
              <form className="form-grid" onSubmit={submitBooking}>
                <label>Nombre<input required value={client.first_name} onChange={(e) => setClient({ ...client, first_name: e.target.value })} /></label>
                <label>Apellido<input required value={client.last_name} onChange={(e) => setClient({ ...client, last_name: e.target.value })} /></label>
                <label>Telefono o WhatsApp<input required value={client.phone} onChange={(e) => setClient({ ...client, phone: e.target.value })} /></label>
                <Summary service={selectedService} date={date} time={time} customer={`${client.first_name} ${client.last_name}`.trim()} />
                <button className="primary" type="submit">Confirmar turno</button>
              </form>
            </section>
          )}

          {step === "confirmation" && (
            <section className="confirmation">
              <div className="success-mark">OK</div>
              <h2>Tu turno fue reservado correctamente</h2>
              <Summary service={selectedService} date={booking.date} time={booking.start_time} customer={`${booking.client_first_name} ${booking.client_last_name}`} />
              {booking.cancellation_token ? (
                <div className="cancel-link-box">
                  <p>Guardá este enlace por si necesitás cancelar tu turno.</p>
                  <div className="confirmation-actions">
                    <button className="ghost" onClick={copyCancellationLink}>Copiar enlace</button>
                    <button className="primary" onClick={openCancellationLink}>Abrir enlace</button>
                  </div>
                  {copyMessage ? <span className="copy-message">{copyMessage}</span> : null}
                </div>
              ) : null}
              <button className="primary" onClick={resetClient}>Finalizar</button>
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
                <label>ContraseÃ±a<input required type="password" value={login.password} onChange={(e) => setLogin({ ...login, password: e.target.value })} /></label>
                <button className="primary" type="submit">Iniciar sesiÃ³n</button>
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
              <div className="agenda-wrap">
                <div className="agenda-head"><span>Hora</span><span>Cliente</span><span>Servicio</span><span>Estado</span><span>Acciones</span></div>
                <div className="agenda-rows">
                  {agenda.map((slot) => (
                    <div key={slot.time} className={`agenda-row ${slot.status === "Libre" ? "free" : slot.status === "Bloqueado" ? "blocked" : "booked"}`}>
                      <strong>{String(slot.time).slice(0, 5)}</strong>
                      <span>{slot.appointment ? `${slot.appointment.client_first_name} ${slot.appointment.client_last_name}` : slot.status === "Bloqueado" ? "Horario bloqueado" : "Disponible"}</span>
                      <span>{slot.appointment?.service_name || "-"}</span>
                      <span className={`status ${slot.status === "Libre" ? "free" : slot.status === "Bloqueado" ? "blocked" : "booked"}`}>{slot.appointment?.origin === "MANUAL" ? "Registrado manualmente" : slot.status}</span>
                      <div className="row-actions">
                        {slot.status === "Libre" && <><button onClick={() => setManual({ time: slot.time, service_id: services[0]?.id || "", first_name: "", last_name: "", phone: "" })}>Registrar</button><button onClick={() => blockSlot(slot)}>Bloquear</button></>}
                        {slot.status === "Reservado" && <button onClick={() => cancelAppointment(slot)}>Cancelar</button>}
                        {slot.status === "Bloqueado" && <button onClick={() => unblockSlot(slot)}>Desbloquear</button>}
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            </section>
          )}
        </main>
      )}

      {manual ? (
        <div className="modal-layer">
          <form className="dialog-card" onSubmit={submitManual}>
            <div><p className="eyebrow">Registrar turno manual</p><h3>{formatDate(adminDate)} Â· {timeLabel(manual.time)}</h3></div>
            <label>Nombre<input required value={manual.first_name} onChange={(e) => setManual({ ...manual, first_name: e.target.value })} /></label>
            <label>Apellido<input value={manual.last_name} onChange={(e) => setManual({ ...manual, last_name: e.target.value })} /></label>
            <label>Telefono <span>opcional</span><input value={manual.phone} onChange={(e) => setManual({ ...manual, phone: e.target.value })} /></label>
            <label>Servicio<select value={manual.service_id} onChange={(e) => setManual({ ...manual, service_id: e.target.value })}>{services.map((service) => <option key={service.id} value={service.id}>{service.name}</option>)}</select></label>
            <menu><button type="button" className="ghost" onClick={() => setManual(null)}>Cerrar</button><button className="primary" type="submit">Guardar</button></menu>
          </form>
        </div>
      ) : null}
    </div>
  );
}


