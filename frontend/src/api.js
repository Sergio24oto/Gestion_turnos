const API_URL = import.meta.env.VITE_API_URL || "http://localhost:8000/api";

async function request(path, options = {}) {
  const token = localStorage.getItem("adminToken");
  const headers = {
    "Content-Type": "application/json",
    ...(options.headers || {}),
  };
  if (token) headers.Authorization = `Bearer ${token}`;
  const response = await fetch(`${API_URL}${path}`, { ...options, headers });
  if (!response.ok) {
    let detail = "Ocurrió un error.";
    try {
      const body = await response.json();
      detail = body.detail || detail;
    } catch {
      detail = response.statusText;
    }
    throw new Error(detail);
  }
  if (response.status === 204) return null;
  return response.json();
}

export const api = {
  services: (barberId = null) => {
    const suffix = barberId ? `?barber_id=${encodeURIComponent(barberId)}` : "";
    return request(`/services${suffix}`);
  },
  adminServices: () => request("/admin/services"),
  createAdminService: (payload) => request("/admin/services", { method: "POST", body: JSON.stringify(payload) }),
  updateAdminService: (id, payload) => request(`/admin/services/${id}`, { method: "PATCH", body: JSON.stringify(payload) }),
  updateAdminServiceStatus: (id, payload) => request(`/admin/services/${id}/status`, { method: "PATCH", body: JSON.stringify(payload) }),
  barbers: () => request("/barbers"),
  availability: (date, barberId = null, serviceId = null) => {
    const suffix = barberId ? `&barber_id=${encodeURIComponent(barberId)}` : "";
    const serviceSuffix = serviceId ? `&service_id=${encodeURIComponent(serviceId)}` : "";
    return request(`/availability?date=${date}${suffix}${serviceSuffix}`);
  },
  createAppointment: (payload) => request("/appointments", { method: "POST", body: JSON.stringify(payload) }),
  login: (payload) => request("/auth/login", { method: "POST", body: JSON.stringify(payload) }),
  agenda: (date) => request(`/appointments/agenda?date_=${date}`),
  createManualAppointment: (payload) => request("/appointments/manual", { method: "POST", body: JSON.stringify(payload) }),
  cancelAppointment: (id) => request(`/appointments/${id}/cancel`, { method: "PATCH" }),
  cancellationDetails: (token) => request(`/appointments/cancel/${encodeURIComponent(token)}`),
  cancelByToken: (token) => request(`/appointments/cancel/${encodeURIComponent(token)}`, { method: "PATCH" }),
  blockSlot: (payload) => request("/blocks", { method: "POST", body: JSON.stringify(payload) }),
  unblockSlot: (id) => request(`/blocks/${id}`, { method: "DELETE" }),
};
