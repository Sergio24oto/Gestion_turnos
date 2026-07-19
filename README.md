# Sistema de turnos para peluqueria

Aplicacion web funcional para gestionar turnos de Marcelo Navarro Peluqueria Unisex.

El prototipo estatico original se conserva en:

`outputs/prototipo-peluqueria`

La version funcional nueva esta organizada en:

- `frontend/`: React + Vite
- `backend/`: FastAPI + SQLAlchemy + MySQL

## Requisitos

- Node.js 20 o superior
- Python 3.11 o superior
- MySQL local escuchando en `localhost:3306`

## 1. Crear la base de datos MySQL local

Entrar a MySQL:

```bash
mysql -u root -p
```

Crear la base de datos:

```sql
CREATE DATABASE peluqueria CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
```

Opcionalmente, crear un usuario propio para la app:

```sql
CREATE USER 'peluqueria_user'@'localhost' IDENTIFIED BY 'TU_PASSWORD_LOCAL';
GRANT ALL PRIVILEGES ON peluqueria.* TO 'peluqueria_user'@'localhost';
FLUSH PRIVILEGES;
```

## 2. Configurar variables de entorno del backend

Copiar el ejemplo:

```bash
cd backend
copy .env.example .env
```

Editar `backend/.env`:

```env
MYSQL_HOST=localhost
MYSQL_PORT=3306
MYSQL_DATABASE=peluqueria
MYSQL_USER=peluqueria_user
MYSQL_PASSWORD=TU_PASSWORD_LOCAL

ADMIN_DEFAULT_USER=admin
ADMIN_DEFAULT_PASSWORD=demo2026
SECRET_KEY=una-clave-local-larga
ACCESS_TOKEN_EXPIRE_MINUTES=480
FRONTEND_ORIGIN=http://localhost:5173
```

No guardes contrasenas reales en `.env.example`.

## 3. Instalar dependencias del backend

Desde la carpeta `backend/`:

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

## 4. Ejecutar FastAPI

Desde `backend/`, con el entorno virtual activo:

```bash
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Al iniciar, FastAPI crea las tablas si no existen y carga:

- servicios iniciales
- usuario admin inicial

Usuario admin por defecto:

- usuario: `admin`
- clave: `demo2026`

## 5. Configurar variables de entorno del frontend

Copiar el ejemplo:

```bash
cd frontend
copy .env.example .env
```

Contenido esperado:

```env
VITE_API_URL=http://localhost:8000/api
```

## 6. Instalar dependencias del frontend

Desde `frontend/`:

```bash
npm install
```

## 7. Ejecutar React

Desde `frontend/`:

```bash
npm run dev
```

Abrir:

```text
http://localhost:5173
```

## 8. Probar la aplicacion localmente

1. Iniciar MySQL.
2. Iniciar FastAPI en `http://localhost:8000`.
3. Iniciar React en `http://localhost:5173`.
4. En la vista publica:
   - seleccionar un servicio;
   - elegir una fecha de martes a sabado;
   - elegir un horario disponible;
   - cargar nombre, apellido y telefono;
   - confirmar el turno.
5. Entrar a `Admin`.
6. Iniciar sesion con `admin` / `demo2026`.
7. Verificar que el turno aparezca en la agenda del dia.
8. Registrar un turno manual o bloquear un horario.
9. Volver al flujo publico y verificar que ese horario ya no aparezca disponible.

## Endpoints principales

- `GET /api/health`
- `POST /api/auth/login`
- `GET /api/services`
- `GET /api/availability?date=YYYY-MM-DD`
- `POST /api/appointments`
- `GET /api/appointments/agenda?date_=YYYY-MM-DD`
- `POST /api/appointments/manual`
- `PATCH /api/appointments/{id}/cancel`
- `POST /api/blocks`
- `DELETE /api/blocks/{id}`

## Tablas

FastAPI crea estas tablas en MySQL:

- `servicios`
- `clientes`
- `turnos`
- `bloqueos_horarios`
- `usuarios_admin`

La tabla `turnos` evita duplicados mediante una restriccion unica para fecha/hora activa. Los turnos cancelados liberan el horario. La tabla `bloqueos_horarios` tambien tiene restriccion unica por fecha/hora.

Las reservas solo se permiten en horarios futuros con al menos 20 minutos de anticipacion. Si la fecha seleccionada es hoy, el frontend oculta los horarios anteriores o demasiado cercanos, y el backend tambien rechaza esas peticiones con HTTP 400 aunque se envien manualmente.

## Cambiar a MySQL remoto

Solo hay que modificar `backend/.env`:

```env
MYSQL_HOST=host-remoto
MYSQL_PORT=3306
MYSQL_DATABASE=peluqueria
MYSQL_USER=usuario-remoto
MYSQL_PASSWORD=password-remoto
```

No hace falta cambiar codigo.
