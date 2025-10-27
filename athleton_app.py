import os
import sqlite3
from datetime import date, datetime, timedelta

import matplotlib.pyplot as plt
import pandas as pd
import streamlit as st

# ===== IA (OpenAI) =====
def get_openai_client():
    """Devuelve un cliente de OpenAI si hay clave; si no, None y el motivo."""
    key = os.getenv("OPENAI_API_KEY", "").strip()
    if not key:
        return None, "Falta OPENAI_API_KEY"
    try:
        from openai import OpenAI
        return OpenAI(api_key=key), None
    except Exception as e:
        return None, f"Error importando openai: {e}"
# ---------------------- DB ----------------------
# Si hay DATABASE_URL usamos PostgreSQL; si no, SQLite (local)
DB_URL = os.getenv("DATABASE_URL", "").strip()
USE_PG = bool(DB_URL)

if USE_PG:
    from sqlalchemy import create_engine, text
    engine = create_engine(DB_URL, pool_pre_ping=True)
else:
    DB_PATH = os.getenv("ATHLETON_DB", "athleton.db")
    import sqlite3

def get_conn():
    if USE_PG:
        return engine.connect()
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    if USE_PG:
        with engine.begin() as conn:
            conn.execute(text("""
            CREATE TABLE IF NOT EXISTS users (
              id SERIAL PRIMARY KEY,
              email TEXT UNIQUE NOT NULL,
              password_hash TEXT NOT NULL,
              name TEXT
            );"""))
            conn.execute(text("""
            CREATE TABLE IF NOT EXISTS profiles (
              user_id INTEGER PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
              sex TEXT, age INTEGER, height_cm REAL, weight_kg REAL,
              objective TEXT, experience TEXT, availability_days INTEGER,
              injuries TEXT, equipment TEXT, diet_pref TEXT, restrictions TEXT,
              sleep_h REAL, stress TEXT,
              kcal_target REAL, carbs_pct REAL, protein_pct REAL, fat_pct REAL,
              updated_at TEXT
            );"""))
            conn.execute(text("""
            CREATE TABLE IF NOT EXISTS plans (
              id SERIAL PRIMARY KEY,
              user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
              weekday INTEGER NOT NULL,
              title TEXT NOT NULL,
              details TEXT
            );"""))
            conn.execute(text("""
            CREATE TABLE IF NOT EXISTS workouts (
              id SERIAL PRIMARY KEY,
              user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
              wdate DATE NOT NULL,
              wtype TEXT NOT NULL,
              duration_min REAL,
              distance_km REAL,
              rpe INTEGER,
              notes TEXT,
              created_at TIMESTAMP NOT NULL
            );"""))
    else:
        conn = get_conn(); cur = conn.cursor()
        cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          email TEXT UNIQUE NOT NULL,
          password_hash TEXT NOT NULL,
          name TEXT
        );""")
        cur.execute("""
        CREATE TABLE IF NOT EXISTS profiles (
          user_id INTEGER PRIMARY KEY,
          sex TEXT, age INTEGER, height_cm REAL, weight_kg REAL,
          objective TEXT, experience TEXT, availability_days INTEGER,
          injuries TEXT, equipment TEXT, diet_pref TEXT, restrictions TEXT,
          sleep_h REAL, stress TEXT,
          kcal_target REAL, carbs_pct REAL, protein_pct REAL, fat_pct REAL,
          updated_at TEXT,
          FOREIGN KEY(user_id) REFERENCES users(id)
        );""")
        cur.execute("""
        CREATE TABLE IF NOT EXISTS plans (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          user_id INTEGER NOT NULL,
          weekday INTEGER NOT NULL,
          title TEXT NOT NULL,
          details TEXT,
          FOREIGN KEY(user_id) REFERENCES users(id)
        );""")
        cur.execute("""
        CREATE TABLE IF NOT EXISTS workouts (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          user_id INTEGER NOT NULL,
          wdate TEXT NOT NULL,
          wtype TEXT NOT NULL,
          duration_min REAL,
          distance_km REAL,
          rpe INTEGER,
          notes TEXT,
          created_at TEXT NOT NULL,
          FOREIGN KEY(user_id) REFERENCES users(id)
        );""")
        conn.commit()

# helpers
def fetchone(query, params):
    if USE_PG:
        with engine.begin() as conn:
            row = conn.execute(text(query), params).mappings().first()
            return row
    else:
        cur = get_conn().cursor(); cur.execute(query, params); return cur.fetchone()

def fetchall(query, params):
    if USE_PG:
        with engine.begin() as conn:
            return list(conn.execute(text(query), params).mappings().all())
    else:
        cur = get_conn().cursor(); cur.execute(query, params); return cur.fetchall()

def execute(query, params):
    if USE_PG:
        with engine.begin() as conn:
            conn.execute(text(query), params)
    else:
        cur = get_conn().cursor(); cur.execute(query, params); cur.connection.commit()

def executemany(query, rows_param_dicts):
    if USE_PG:
        with engine.begin() as conn:
            conn.execute(text(query), rows_param_dicts)
    else:
        cur = get_conn().cursor()
        cur.executemany(query, [tuple(d.values()) for d in rows_param_dicts])
        cur.connection.commit()

# USERS
def get_user_by_email(email):
    if USE_PG:
        return fetchone("SELECT id,email,password_hash,name FROM users WHERE LOWER(email)=LOWER(:email)", {"email": email.lower()})
    return fetchone("SELECT * FROM users WHERE email=?", (email.lower(),))

def create_user(email, password, name):
    import hashlib
    pw = hashlib.sha256(password.encode("utf-8")).hexdigest()
    if USE_PG:
        with engine.begin() as conn:
            new_id = conn.execute(
                text("INSERT INTO users (email,password_hash,name) VALUES (:e,:p,:n) RETURNING id"),
                {"e": email.lower(), "p": pw, "n": name}
            ).scalar_one()
            return new_id
    else:
        cur = get_conn().cursor()
        cur.execute("INSERT INTO users (email,password_hash,name) VALUES (?,?,?)", (email.lower(), pw, name))
        cur.connection.commit()
        return cur.lastrowid

# PROFILES
def get_profile(user_id):
    if USE_PG:
        return fetchone("SELECT * FROM profiles WHERE user_id=:uid", {"uid": user_id})
    return fetchone("SELECT * FROM profiles WHERE user_id=?", (user_id,))

def upsert_profile(user_id, **kwargs):
    fields = ["sex","age","height_cm","weight_kg","objective","experience","availability_days","injuries","equipment","diet_pref","restrictions","sleep_h","stress","kcal_target","carbs_pct","protein_pct","fat_pct"]
    data = {k: kwargs.get(k) for k in fields}
    data["updated_at"] = datetime.utcnow().isoformat()
    data["user_id"] = user_id

    if USE_PG:
        execute("""
        INSERT INTO profiles (user_id, sex, age, height_cm, weight_kg, objective, experience, availability_days, injuries, equipment, diet_pref, restrictions, sleep_h, stress, kcal_target, carbs_pct, protein_pct, fat_pct, updated_at)
        VALUES (:user_id, :sex, :age, :height_cm, :weight_kg, :objective, :experience, :availability_days, :injuries, :equipment, :diet_pref, :restrictions, :sleep_h, :stress, :kcal_target, :carbs_pct, :protein_pct, :fat_pct, :updated_at)
        ON CONFLICT (user_id) DO UPDATE SET
          sex=EXCLUDED.sex, age=EXCLUDED.age, height_cm=EXCLUDED.height_cm, weight_kg=EXCLUDED.weight_kg,
          objective=EXCLUDED.objective, experience=EXCLUDED.experience, availability_days=EXCLUDED.availability_days,
          injuries=EXCLUDED.injuries, equipment=EXCLUDED.equipment, diet_pref=EXCLUDED.diet_pref, restrictions=EXCLUDED.restrictions,
          sleep_h=EXCLUDED.sleep_h, stress=EXCLUDED.stress,
          kcal_target=EXCLUDED.kcal_target, carbs_pct=EXCLUDED.carbs_pct, protein_pct=EXCLUDED.protein_pct, fat_pct=EXCLUDED.fat_pct,
          updated_at=EXCLUDED.updated_at
        """, data)
    else:
        existing = get_profile(user_id)
        if existing:
            sets = ", ".join([f"{k}=?" for k in ["sex","age","height_cm","weight_kg","objective","experience","availability_days","injuries","equipment","diet_pref","restrictions","sleep_h","stress","kcal_target","carbs_pct","protein_pct","fat_pct","updated_at"]])
            vals = [data[k] for k in ["sex","age","height_cm","weight_kg","objective","experience","availability_days","injuries","equipment","diet_pref","restrictions","sleep_h","stress","kcal_target","carbs_pct","protein_pct","fat_pct","updated_at"]] + [user_id]
            execute(f"UPDATE profiles SET {sets} WHERE user_id=?", tuple(vals))
        else:
            cols = ",".join(["user_id"] + [k for k in data.keys() if k!="user_id"])
            placeholders = ",".join(["?"]*(1+len(data)-1))
            vals = [user_id] + [data[k] for k in data.keys() if k!="user_id"]
            execute(f"INSERT INTO profiles ({cols}) VALUES ({placeholders})", tuple(vals))

def needs_onboarding(user_id):
    p = get_profile(user_id)
    if not p: return True
    required = ["objective","experience","availability_days"]
    return any((p[r] is None or p[r]=="" or (r=="availability_days" and (p[r] or 0)<2)) for r in required)

# PLANS
def get_plan(user_id):
    if USE_PG:
        return fetchall("SELECT * FROM plans WHERE user_id=:uid ORDER BY weekday ASC", {"uid": user_id})
    return fetchall("SELECT * FROM plans WHERE user_id=? ORDER BY weekday ASC", (user_id,))

def set_plan(user_id, items):
    if USE_PG:
        execute("DELETE FROM plans WHERE user_id=:uid", {"uid": user_id})
        rows = [{"uid": user_id, "wd": wd, "t": t, "d": d} for (wd,t,d) in items]
        executemany("INSERT INTO plans (user_id,weekday,title,details) VALUES (:uid,:wd,:t,:d)", rows)
    else:
        execute("DELETE FROM plans WHERE user_id=?", (user_id,))
        cur = get_conn().cursor()
        cur.executemany("INSERT INTO plans (user_id,weekday,title,details) VALUES (?,?,?,?)", [(user_id, wd, t, d) for (wd,t,d) in items])
        cur.connection.commit()

# WORKOUTS
def insert_workout(user_id, wdate, wtype, duration_min, distance_km, rpe, notes):
    now = datetime.utcnow().isoformat()
    if USE_PG:
        execute(
            "INSERT INTO workouts (user_id,wdate,wtype,duration_min,distance_km,rpe,notes,created_at) VALUES (:u,:wd,:wt,:dur,:dist,:rpe,:notes,:now)",
            {"u": user_id, "wd": wdate.isoformat(), "wt": wtype, "dur": duration_min, "dist": distance_km, "rpe": rpe, "notes": notes, "now": now}
        )
    else:
        execute(
            "INSERT INTO workouts (user_id,wdate,wtype,duration_min,distance_km,rpe,notes,created_at) VALUES (?,?,?,?,?,?,?,?)",
            (user_id, wdate.isoformat(), wtype, duration_min, distance_km, rpe, notes, now)
        )

def get_workouts(user_id, start=None, end=None):
    if USE_PG:
        import pandas as pd
        query = "SELECT wdate::date AS wdate, wtype, duration_min, distance_km, rpe, notes FROM workouts WHERE user_id=:u"
        params = {"u": user_id}
        if start:
            query += " AND wdate >= :s"; params["s"] = start.isoformat()
        if end:
            query += " AND wdate <= :e"; params["e"] = end.isoformat()
        query += " ORDER BY wdate DESC"
        return pd.read_sql(text(query), engine, params=params, parse_dates=["wdate"])
    else:
        import pandas as pd
        conn = get_conn()
        q = "SELECT wdate,wtype,duration_min,distance_km,rpe,notes FROM workouts WHERE user_id=?"
        params=[user_id]
        if start: q+=" AND date(wdate) >= date(?)"; params.append(start.isoformat())
        if end: q+=" AND date(wdate) <= date(?)"; params.append(end.isoformat())
        q+=" ORDER BY wdate DESC"
        return pd.read_sql_query(q, conn, params=params, parse_dates=["wdate"])
# ---------------------- fin DB ----------------------

import hashlib
def hash_pw(pw): return hashlib.sha256(pw.encode("utf-8")).hexdigest()

def get_user_by_email(email):
    c=get_conn().cursor(); c.execute("SELECT * FROM users WHERE email=?",(email.lower(),)); return c.fetchone()

def create_user(email, password, name):
    c=get_conn().cursor()
    c.execute("INSERT INTO users (email,password_hash,name) VALUES (?,?,?)",
              (email.lower(), hash_pw(password), name))
    c.connection.commit()
    return c.lastrowid

# ---------- Profile helpers ----------
def get_profile(user_id):
    c=get_conn().cursor(); c.execute("SELECT * FROM profiles WHERE user_id=?",(user_id,)); return c.fetchone()

def upsert_profile(user_id, **kwargs):
    c=get_conn().cursor()
    existing = get_profile(user_id)
    fields = ["sex","age","height_cm","weight_kg","objective","experience","availability_days","injuries","equipment","diet_pref","restrictions","sleep_h","stress","kcal_target","carbs_pct","protein_pct","fat_pct"]
    data = {k: kwargs.get(k) for k in fields}
    data["updated_at"] = datetime.utcnow().isoformat()
    if existing:
        sets = ", ".join([f"{k} = ?" for k in data.keys()])
        c.execute(f"UPDATE profiles SET {sets} WHERE user_id = ?", [*data.values(), user_id])
    else:
        cols = ", ".join(["user_id"] + list(data.keys()))
        qs = ", ".join(["?"] * (1 + len(data)))
        c.execute(f"INSERT INTO profiles ({cols}) VALUES ({qs})", [user_id, *data.values()])
    c.connection.commit()

def needs_onboarding(user_id):
    p = get_profile(user_id)
    if not p: return True
    required = ["objective","experience","availability_days"]
    return any((p[r] is None or p[r]=="" or (r=="availability_days" and (p[r] or 0)<2)) for r in required)

# ---------- Plan helpers ----------
WEEKDAY_ES = ["Lunes","Martes","Miércoles","Jueves","Viernes","Sábado","Domingo"]

def get_plan(user_id):
    c=get_conn().cursor()
    c.execute("SELECT * FROM plans WHERE user_id=? ORDER BY weekday ASC",(user_id,))
    return c.fetchall()

def set_plan(user_id, items):
    c=get_conn().cursor()
    c.execute("DELETE FROM plans WHERE user_id=?", (user_id,))
    c.executemany("INSERT INTO plans (user_id,weekday,title,details) VALUES (?,?,?,?)",
                  [(user_id, wd, t, d) for (wd,t,d) in items])
    c.connection.commit()

def generate_plan_from_profile(p):
    days = max(2, min(int(p["availability_days"] or 3), 7))
    obj = (p["objective"] or "").lower()
    exp = (p["experience"] or "principiante").lower()

    strength = "Fuerza (full body)" if "princip" in exp else "Fuerza (empuje/tirón/piernas)"
    easy_run = "Cardio Z2 (suave)"; hiit="HIIT (intervalos)"; long_run="Cardio largo Z2"
    mobility="Movilidad + core"; rest="Descanso / rec. activa"

    if "múscul" in obj or "hipertrof" in obj:
        template=[strength,strength,easy_run,strength,mobility,(long_run if days>=6 else rest),rest]
    elif "grasa" in obj or "perder" in obj:
        template=[strength,hiit,mobility,strength,easy_run,long_run,rest]
    elif "10k" in obj or "marat" in obj:
        tempo="Tempo (umbral)"; intervals="Series (VO2)"
        template=[easy_run,strength,intervals,easy_run,strength,long_run,rest]
        if "marat" in obj: template[2]=tempo
    elif "triatl" in obj:
        template=["Natación técnica","Fuerza","Bici Z2","Transición (bici+carrera)","Natación velocidad","Carrera Z2",rest]
    else:
        template=[strength,easy_run,mobility,strength,hiit,long_run,rest]

    items=[]
    for i in range(7):
        title = template[i] if i < days else rest
        items.append((i, title, default_details_for_session(title, exp)))
    return items

def default_details_for_session(title, exp):
    exp_s = "Principiante" if "princip" in exp else ("Intermedio" if "inter" in exp else "Avanzado")
    if "Fuerza" in title:
        if "full body" in title.lower(): return f"{exp_s}: 3x(Prensa/remo/press) 8-12 reps, 60-90''; core 10'."
        return f"{exp_s}: Empuje/Tirón/Piernas 3-4x6-10; core 10'."
    if "HIIT" in title: return f"{exp_s}: 8-12 × (1' fuerte / 1' suave)."
    if "largo" in title.lower(): return f"{exp_s}: 60-90' Z2 continuo."
    if "Z2" in title: return f"{exp_s}: 30-50' cómodo (hablar en frases)."
    if "Tempo" in title: return f"{exp_s}: 2x15' a umbral (RPE 7-8), rec 5'."
    if "Series" in title or "VO2" in title: return f"{exp_s}: 5-8x3' fuerte (RPE 8-9) / 2' suave."
    if "Movilidad" in title: return "Caderas/hombros/torácica 20', respiración 5'."
    if "Natación" in title: return "Técnica 6x50m, pull 4x100m, patada 8x25m."
    if "Bici" in title: return "60' Z2, cadencia 85-95 rpm."
    if "Transición" in title: return "Bici 40' Z2 + carrera 15' Z2."
    return ""

# ---------- Nutrición ----------
def mifflin_st_jeor(sex, age, weight_kg, height_cm):
    s = 5 if (sex or "").upper() == "M" else -161
    return 10*weight_kg + 6.25*height_cm - 5*age + s

def estimate_targets(profile):
    if not profile or not all(profile.get(k) for k in ["sex","age","weight_kg","height_cm"]):
        return (2200.0, 45.0, 30.0, 25.0)
    bmr = mifflin_st_jeor(profile["sex"], int(profile["age"]), float(profile["weight_kg"]), float(profile["height_cm"]))
    days = profile.get("availability_days") or 3
    pal = 1.45 if days <= 3 else (1.6 if days <= 5 else 1.75)
    tdee = bmr * pal
    obj = (profile.get("objective") or "").lower()
    if "grasa" in obj or "perder" in obj: kcal = tdee * 0.85
    elif "múscul" in obj or "hipertrof" in obj: kcal = tdee * 1.10
    else: kcal = tdee
    if "múscul" in obj: carbs, protein, fat = 40.0, 30.0, 30.0
    elif "grasa" in obj: carbs, protein, fat = 35.0, 35.0, 30.0
    elif "10k" in obj or "marat" in obj or "triatl" in obj: carbs, protein, fat = 50.0, 25.0, 25.0
    else: carbs, protein, fat = 45.0, 30.0, 25.0
    return (round(kcal,1), carbs, protein, fat)

# ---------- Workouts ----------
def insert_workout(user_id, wdate, wtype, duration_min, distance_km, rpe, notes):
    c=get_conn().cursor()
    c.execute("INSERT INTO workouts (user_id,wdate,wtype,duration_min,distance_km,rpe,notes,created_at) VALUES (?,?,?,?,?,?,?,?)",
              (user_id, wdate.isoformat(), wtype, duration_min, distance_km, rpe, notes, datetime.utcnow().isoformat()))
    c.connection.commit()

def get_workouts(user_id, start=None, end=None):
    conn=get_conn()
    query="SELECT wdate,wtype,duration_min,distance_km,rpe,notes FROM workouts WHERE user_id=?"
    params=[user_id]
    if start: query+=" AND date(wdate) >= date(?)"; params.append(start.isoformat())
    if end: query+=" AND date(wdate) <= date(?)"; params.append(end.isoformat())
    query+=" ORDER BY wdate DESC"
    df=pd.read_sql_query(query, conn, params=params, parse_dates=["wdate"])
    return df

# ---------- IA ----------
def ai_coach_response(prompt, profile, workouts_df):
    client, err = get_openai_client()
    if not client:
        return f"(IA desactivada) {err}. Añade la variable en Render → Settings → Environment."

    try:
        ctx = f"Perfil: {dict(profile) if profile else {}}\n\nEntrenos recientes:\n{workouts_df.head(50).to_string(index=False)}"
        user_msg = (
            "Eres un entrenador y nutricionista. Responde con pasos concretos, seguros y personalizados.\n"
            f"Pregunta: {prompt}\n\nContexto:\n{ctx}\n"
        )
        resp = client.chat.completions.create(
            model="gpt-4o-mini",
            temperature=0.4,
            messages=[
                {"role": "system", "content": "Coach experto. Sé específico, breve y seguro."},
                {"role": "user", "content": user_msg},
            ],
            max_tokens=450,
        )
        return resp.choices[0].message.content.strip()
    except Exception as e:
        return f"No se pudo llamar a la IA: {e}"

# ---------------------- UI ----------------------
def login_view():
    st.header("Inicia sesión")
    email = st.text_input("Email", key="login_email")
    password = st.text_input("Contraseña", type="password", key="login_password")
    if st.button("Entrar", type="primary", use_container_width=True):
        u = get_user_by_email(email.strip())
        if not u or u["password_hash"] != hash_pw(password):
            st.error("Credenciales no válidas.")
        else:
            st.session_state["user"] = dict(u)
            st.rerun()

def signup_view():
    st.header("Crear cuenta")
    name = st.text_input("Nombre", key="signup_name")
    email = st.text_input("Email", key="signup_email")
    password = st.text_input("Contraseña", type="password", key="signup_password")
    if st.button("Registrarme", type="primary", use_container_width=True):
        if get_user_by_email(email.strip()):
            st.error("Ese email ya existe.")
        else:
            try:
                create_user(email.strip(), password, name.strip() or None)
                st.success("Cuenta creada. Ahora puedes iniciar sesión.")
            except Exception as e:
                st.error(f"No se pudo crear la cuenta: {e}")

def onboarding_view(user_id):
    st.header("Tu perfil de atleta")
    st.markdown("Completa estas preguntas para personalizar tu plan y las recomendaciones.")
    with st.form("onboarding"):
        col1, col2 = st.columns(2)
        with col1:
            sex = st.selectbox("Sexo", ["M","F","Otro/Prefiero no decir"])
            age = st.number_input("Edad", min_value=12, max_value=90, value=30)
            height_cm = st.number_input("Altura (cm)", min_value=120.0, max_value=230.0, value=175.0, step=0.5)
            weight_kg = st.number_input("Peso (kg)", min_value=35.0, max_value=250.0, value=70.0, step=0.5)
            sleep_h = st.number_input("Horas de sueño/día", min_value=3.0, max_value=12.0, value=7.0, step=0.5)
            stress = st.selectbox("Estrés percibido", ["Bajo","Medio","Alto"])
        with col2:
            objective = st.selectbox("Objetivo principal", ["Perder grasa","Ganar músculo","Correr 10K","Media maratón","Maratón","Triatlón sprint/olímpico","Mejorar salud general"])
            experience = st.selectbox("Experiencia", ["Principiante","Intermedio","Avanzado"])
            availability_days = st.slider("¿Cuántos días/semana puedes entrenar?", 2, 7, 4)
            equipment = st.multiselect("Material disponible", ["Ninguno","Mancuernas","Barra y discos","Bandas","Kettlebell","Máquinas gimnasio"], default=["Ninguno"])
            injuries = st.text_input("Lesiones/limitaciones (opcional)")
            diet_pref = st.selectbox("Preferencia dietaria", ["Omnívoro","Vegetariano","Vegano","Flexitariano","Otra"])
            restrictions = st.text_input("Alergias/intolerancias (opcional)")
        submitted = st.form_submit_button("Guardar y generar plan", use_container_width=True)
    if submitted:
        kcal, c, p, f = estimate_targets({
            "sex": sex, "age": age, "weight_kg": weight_kg, "height_cm": height_cm,
            "availability_days": availability_days, "objective": objective
        })
        upsert_profile(
            user_id,
            sex=sex, age=int(age), height_cm=float(height_cm), weight_kg=float(weight_kg),
            objective=objective, experience=experience, availability_days=int(availability_days),
            injuries=injuries, equipment=", ".join(equipment) if equipment else "Ninguno",
            diet_pref=diet_pref, restrictions=restrictions, sleep_h=float(sleep_h), stress=stress,
            kcal_target=kcal, carbs_pct=c, protein_pct=p, fat_pct=f
        )
        set_plan(user_id, generate_plan_from_profile(get_profile(user_id)))
        st.success("Perfil guardado y plan generado.")
        st.rerun()

def profile_view(user_id):
    st.subheader("Perfil")
    p = get_profile(user_id)
    if not p:
        st.info("Completa el perfil para personalizar tu plan."); onboarding_view(user_id); return

    with st.expander("Datos personales y preferencias", expanded=True):
        with st.form("edit_profile"):
            col1, col2, col3 = st.columns(3)
            with col1:
                sex = st.selectbox("Sexo", ["M","F","Otro/Prefiero no decir"], index=["M","F","Otro/Prefiero no decir"].index(p["sex"] or "M"))
                age = st.number_input("Edad", min_value=12, max_value=90, value=int(p["age"] or 30))
                height_cm = st.number_input("Altura (cm)", min_value=120.0, max_value=230.0, value=float(p["height_cm"] or 175.0), step=0.5)
                weight_kg = st.number_input("Peso (kg)", min_value=35.0, max_value=250.0, value=float(p["weight_kg"] or 70.0), step=0.5)
            with col2:
                objectives = ["Perder grasa","Ganar músculo","Correr 10K","Media maratón","Maratón","Triatlón sprint/olímpico","Mejorar salud general"]
                objective = st.selectbox("Objetivo", objectives, index=objectives.index(p["objective"] or "Perder grasa"))
                experience = st.selectbox("Experiencia", ["Principiante","Intermedio","Avanzado"], index=["Principiante","Intermedio","Avanzado"].index(p["experience"] or "Principiante"))
                availability_days = st.slider("Días/semana", 2, 7, value=int(p["availability_days"] or 4))
                injuries = st.text_input("Lesiones/limitaciones", value=p["injuries"] or "")
            with col3:
                equipment = st.text_input("Material disponible", value=p["equipment"] or "Ninguno")
                diet_pref = st.selectbox("Dieta", ["Omnívoro","Vegetariano","Vegano","Flexitariano","Otra"], index=["Omnívoro","Vegetariano","Vegano","Flexitariano","Otra"].index(p["diet_pref"] or "Omnívoro"))
                restrictions = st.text_input("Alergias/intolerancias", value=p["restrictions"] or "")
                sleep_h = st.number_input("Horas de sueño", min_value=3.0, max_value=12.0, value=float(p["sleep_h"] or 7.0), step=0.5)
                stress = st.selectbox("Estrés", ["Bajo","Medio","Alto"], index=["Bajo","Medio","Alto"].index(p["stress"] or "Medio"))
            if st.form_submit_button("Guardar cambios y regenerar plan", use_container_width=True):
                kcal, c, pr, fa = estimate_targets({
                    "sex": sex, "age": age, "weight_kg": weight_kg, "height_cm": height_cm,
                    "availability_days": availability_days, "objective": objective
                })
                upsert_profile(
                    user_id,
                    sex=sex, age=int(age), height_cm=float(height_cm), weight_kg=float(weight_kg),
                    objective=objective, experience=experience, availability_days=int(availability_days),
                    injuries=injuries, equipment=equipment, diet_pref=diet_pref, restrictions=restrictions,
                    sleep_h=float(sleep_h), stress=stress,
                    kcal_target=kcal, carbs_pct=c, protein_pct=pr, fat_pct=fa
                )
                set_plan(user_id, generate_plan_from_profile(get_profile(user_id)))
                st.success("Perfil actualizado y plan regenerado.")

    p = get_profile(user_id)
    st.markdown("### Nutrición estimada")
    kcal = p["kcal_target"] or 2200
    c, pr, fa = p["carbs_pct"] or 45, p["protein_pct"] or 30, p["fat_pct"] or 25
    st.write(f"Objetivo calórico: **{kcal:.0f} kcal/día**")
    col1, col2, col3 = st.columns(3)
    with col1: st.metric("Carbohidratos", f"{c:.0f}%")
    with col2: st.metric("Proteínas", f"{pr:.0f}%")
    with col3: st.metric("Grasas", f"{fa:.0f}%")
    st.caption(f"≈ {(kcal*(c/100))/4:.0f} g CH / {(kcal*(pr/100))/4:.0f} g PROT / {(kcal*(fa/100))/9:.0f} g GRAS/día")

def weekly_plan_view(user_id):
    st.subheader("Plan semanal")
    plan = get_plan(user_id)
    cols = st.columns(7)
    for i, col in enumerate(cols):
        with col:
            st.caption(WEEKDAY_ES[i])
            row = next((p for p in plan if p["weekday"] == i), None)
            title = row["title"] if row else "—"
            details = row["details"] if row else ""
            st.write(f"**{title}**")
            if details: st.write(details)

def log_workout_view(user_id):
    st.subheader("Registrar sesión")
    today = date.today()
    wdate = st.date_input("Fecha", value=today)
    wtype = st.selectbox("Tipo", ["Fuerza","Cardio","HIIT","Movilidad","Descanso activo","Otro"])
    col1, col2 = st.columns(2)
    with col1: duration = st.number_input("Duración (min)", min_value=0.0, step=5.0)
    with col2: distance = st.number_input("Distancia (km)", min_value=0.0, step=0.5)
    rpe = st.slider("Esfuerzo percibido (RPE 1-10)", min_value=1, max_value=10, value=6)
    notes = st.text_area("Notas")
    if st.button("Guardar sesión", type="primary", use_container_width=True):
        insert_workout(user_id, wdate, wtype, duration or None, distance or None, rpe or None, notes or None)
        st.success("Sesión registrada.")

def history_view(user_id):
    st.subheader("Historial y progreso")
    col1, col2 = st.columns(2)
    with col1: start = st.date_input("Desde", value=date.today()-timedelta(days=30))
    with col2: end = st.date_input("Hasta", value=date.today())
    df = get_workouts(user_id, start, end)
    if df.empty: st.info("Sin registros aún."); return
    st.dataframe(df)

    df["week"] = df["wdate"].dt.to_period("W").apply(lambda r: r.start_time.date())
    agg = df.groupby("week")["duration_min"].sum().reset_index()
    fig1, ax1 = plt.subplots(); ax1.plot(agg["week"], agg["duration_min"], marker="o")
    ax1.set_title("Minutos entrenados por semana"); ax1.set_xlabel("Semana"); ax1.set_ylabel("Minutos")
    st.pyplot(fig1)

    if "distance_km" in df and df["distance_km"].notna().any():
        agg2 = df.groupby("week")["distance_km"].sum().reset_index()
        fig2, ax2 = plt.subplots(); ax2.bar(agg2["week"].astype(str), agg2["distance_km"])
        ax2.set_title("Kilómetros por semana"); ax2.set_xlabel("Semana"); ax2.set_ylabel("Km")
        st.pyplot(fig2)

def insights_view(user_id):
    st.subheader("Insights de progreso")
    df = get_workouts(user_id, date.today()-timedelta(days=56), date.today())
    if df.empty: st.info("Registra al menos 1-2 semanas para ver insights."); return
    df["week"] = df["wdate"].dt.to_period("W").apply(lambda r: r.start_time.date())
    vol = df.groupby("week")["duration_min"].sum().reset_index()
    trend = "⬆️" if len(vol)>=2 and vol["duration_min"].iloc[-1] > vol["duration_min"].iloc[-2] else ("➡️" if len(vol)>=2 else "—")
    st.write(f"Volumen última semana: **{vol['duration_min'].iloc[-1]:.0f} min** ({trend})")
    if df["distance_km"].notna().any():
        dist = df.groupby("week")["distance_km"].sum().reset_index()
        st.write(f"Kilómetros última semana: **{dist['distance_km'].iloc[-1]:.1f} km**")
    if AI_ENABLED:
        st.caption("Resumen generado por IA:")
        prof = dict(get_profile(user_id) or {})
        st.write(ai_coach_response("Resume el progreso y da 3 recomendaciones accionables.", prof, df))
    else:
        st.caption("IA no configurada (añade OPENAI_API_KEY).")

# ---------------------- App ----------------------
def main():
    st.set_page_config(page_title="AthletON", page_icon="🏃", layout="wide")
    init_db()

    st.sidebar.title("AthletON")
    if "user" not in st.session_state:
        st.title("Bienvenido a AthletON")
        tab_login, tab_signup = st.tabs(["Iniciar sesión","Crear cuenta"])
        with tab_login: login_view()
        with tab_signup: signup_view()
        st.caption("MVP de demostración. Datos locales en SQLite (no persistentes en Free).")
        return

    user = st.session_state["user"]
    st.sidebar.write(f"**{user.get('name') or user['email']}**")
    if st.sidebar.button("Cerrar sesión"): del st.session_state["user"]; st.rerun()

    if needs_onboarding(user["id"]): onboarding_view(user["id"]); return

    st.title("Panel AthletON")
    tab1, tab2, tab3, tab4, tab5 = st.tabs(["Plan","Registrar","Historial","Perfil","Coach IA"])
    with tab1: weekly_plan_view(user_id=user["id"])
    with tab2: log_workout_view(user_id=user["id"])
    with tab3: history_view(user_id=user["id"]); st.divider(); insights_view(user_id=user["id"])
    with tab4: profile_view(user_id=user["id"])
    with tab5:
        st.subheader("Coach IA personalizado")
        st.caption("Usa tu perfil e historial. (Configura OPENAI_API_KEY)")
        q = st.text_area("Tu pregunta")
        if st.button("Preguntar", type="primary"):
            prof = dict(get_profile(user["id"]) or {})
            df_last = get_workouts(user["id"], date.today()-timedelta(days=60), date.today())
            st.write(ai_coach_response(q, prof, df_last))

if __name__ == "__main__":
    main()
