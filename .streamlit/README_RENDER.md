# AthletON — MVP con IA (Render Ready)

Incluye:
- Onboarding y perfil de usuario (SQLite)
- Generación de plan semanal
- Registro e historial + gráficas
- **Coach IA** (requiere `OPENAI_API_KEY`)
- Insights de progreso

## Deploy en Render (plan Free)
1. Sube esta carpeta a un repo de GitHub (p. ej. `athleton`).
2. En Render → New → Web Service → conecta el repo (Docker autodetectado).
3. Region: EU (Frankfurt), Branch: main, Root Directory: vacío, Plan: Free.
4. Create Web Service.

### Activar la IA
En Render → tu servicio → **Settings → Environment**:
- Añade variable **OPENAI_API_KEY** con tu clave.
- Despliega de nuevo: **Manual Deploy → Clear build cache & deploy**.
