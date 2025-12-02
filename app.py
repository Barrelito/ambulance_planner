import pandas as pd
import calendar
from io import BytesIO
from flask import Flask, render_template, request, redirect, url_for, send_file, flash, session
from database import db
from datetime import date, datetime, timedelta

# Initiera appen
app = Flask(__name__)

# INSTÄLLNINGAR
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///ambulans.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.secret_key = 'hemlig' # Detta krävs för att sessioner (inloggning) ska funka

# LÖSENORD FÖR ATT KOMMA IN
SYSTEM_PASSWORD = "ambulans112"

db.init_app(app)

from models import *

# -------------------------------------------------------------------
#  SÄKERHET: KONTROLLERA INLOGGNING PÅ ALLA SIDOR
# -------------------------------------------------------------------
@app.before_request
def require_login():
    # Tillåt trafik till inloggningssidan och statiska filer (css/js)
    allowed_routes = ['login', 'static']
    if request.endpoint not in allowed_routes and 'logged_in' not in session:
        return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        password = request.form.get('password')
        if password == SYSTEM_PASSWORD:
            session['logged_in'] = True
            return redirect(url_for('index'))
        else:
            flash("Fel lösenord. Försök igen.")
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.pop('logged_in', None)
    return redirect(url_for('login'))

# -------------------------------------------------------------------
#  HUVUDSIDAN (PLANERING)
# -------------------------------------------------------------------
@app.route('/')
def index():
    selected_date_str = request.args.get('date')
    if not selected_date_str:
        selected_date = date.today()
        selected_date_str = selected_date.strftime('%Y-%m-%d')
    else:
        try:
            selected_date = datetime.strptime(selected_date_str, '%Y-%m-%d').date()
        except ValueError:
            selected_date = date.today()
            selected_date_str = selected_date.strftime('%Y-%m-%d')

    prev_date = (selected_date - timedelta(days=1)).strftime('%Y-%m-%d')
    next_date = (selected_date + timedelta(days=1)).strftime('%Y-%m-%d')

    all_stations = Station.query.all()
    all_users = User.query.order_by(User.home_station, User.name).all() 
    shifts = Shift.query.filter_by(date=selected_date_str).all()

    shift_map = {}
    busy_users = {}

    for shift in shifts:
        if shift.unit_id not in shift_map: shift_map[shift.unit_id] = {}
        shift_map[shift.unit_id][shift.period] = shift

        if shift.amb_id:
            if shift.amb_id not in busy_users: busy_users[shift.amb_id] = {}
            busy_users[shift.amb_id][shift.period] = shift.unit.name
        if shift.vub_id:
            if shift.vub_id not in busy_users: busy_users[shift.vub_id] = {}
            busy_users[shift.vub_id][shift.period] = shift.unit.name

    # Hitta vakanta bilar för flytt-listan
    vacant_spots = []
    all_units = Unit.query.all()
    for unit in all_units:
        if 'BLANKPASS' in unit.station.name: continue
        s_dag = shift_map.get(unit.id, {}).get('Dag')
        if not s_dag or not s_dag.amb_id or not s_dag.vub_id:
            vacant_spots.append({'id': unit.id, 'name': unit.name, 'period': 'Dag', 'station': unit.station.name})
        s_natt = shift_map.get(unit.id, {}).get('Natt')
        if not s_natt or not s_natt.amb_id or not s_natt.vub_id:
            vacant_spots.append({'id': unit.id, 'name': unit.name, 'period': 'Natt', 'station': unit.station.name})
        if unit.mid_time:
            s_mid = shift_map.get(unit.id, {}).get('Mellan')
            if not s_mid or not s_mid.amb_id or not s_mid.vub_id:
                vacant_spots.append({'id': unit.id, 'name': unit.name, 'period': 'Mellan', 'station': unit.station.name})

    return render_template('index.html', 
                           stations=all_stations, shift_map=shift_map, users=all_users, busy_users=busy_users, 
                           current_date=selected_date_str, prev_date=prev_date, next_date=next_date, vacant_spots=vacant_spots)

@app.route('/update_shift', methods=['POST'])
def update_shift():
    target_date = request.form.get('date') 
    unit_id = request.form.get('unit_id')
    period = request.form.get('period')
    new_amb_id = int(request.form.get('amb_id')) if request.form.get('amb_id') else None
    new_vub_id = int(request.form.get('vub_id')) if request.form.get('vub_id') else None

    unit = Unit.query.get(unit_id)
    station_anchor = f"station-{unit.station.id}" if unit else ""

    def clear_from_blankpass(user_id):
        if not user_id: return
        user_shifts = Shift.query.filter_by(date=target_date, period=period).all()
        for s in user_shifts:
            if 'BLANKPASS' in s.unit.station.name:
                if s.amb_id == user_id: s.amb_id = None
                if s.vub_id == user_id: s.vub_id = None

    clear_from_blankpass(new_amb_id)
    clear_from_blankpass(new_vub_id)

    shift = Shift.query.filter_by(date=target_date, unit_id=unit_id, period=period).first()
    if not shift:
        shift = Shift(date=target_date, unit_id=unit_id, period=period)
        db.session.add(shift)

    shift.amb_id = new_amb_id
    shift.vub_id = new_vub_id
    db.session.commit()
    
    return redirect(url_for('index', date=target_date, _anchor=station_anchor))

@app.route('/move_staff', methods=['POST'])
def move_staff():
    date_str = request.form.get('date')
    person_id = int(request.form.get('person_id'))
    target_value = request.form.get('target_spot') 
    if not target_value: return redirect(url_for('index', date=date_str))

    target_unit_id, target_period = target_value.split('|')
    target_unit_id = int(target_unit_id)

    old_shifts = Shift.query.filter_by(date=date_str).all()
    for s in old_shifts:
        if s.amb_id == person_id: s.amb_id = None
        if s.vub_id == person_id: s.vub_id = None
    
    shift = Shift.query.filter_by(date=date_str, unit_id=target_unit_id, period=target_period).first()
    if not shift:
        shift = Shift(date=date_str, unit_id=target_unit_id, period=target_period)
        db.session.add(shift)
    
    if not shift.amb_id: shift.amb_id = person_id
    elif not shift.vub_id: shift.vub_id = person_id
    else: flash("Bilen var tyvärr full.", "warning")

    db.session.commit()
    unit = Unit.query.get(target_unit_id)
    return redirect(url_for('index', date=date_str, _anchor=f"station-{unit.station.id}"))

# -------------------------------------------------------------------
#  DASHBOARD & ADMIN (SAMMA SOM FÖRUT)
# -------------------------------------------------------------------
@app.route('/dashboard')
def dashboard():
    users = User.query.order_by(User.home_station, User.name).all()
    stations = Station.query.all()
    today = date.today()
    sel_year = request.args.get('year', type=int, default=today.year)
    sel_month = request.args.get('month', type=int, default=today.month)
    sel_week = request.args.get('week', type=int, default=0)
    start_date = None
    end_date = None
    filter_label = ""
    if sel_week > 0:
        d = f"{sel_year}-W{sel_week}"
        start_date = datetime.strptime(d + '-1', "%Y-W%W-%w").date()
        end_date = start_date + timedelta(days=6)
        filter_label = f"Vecka {sel_week}, {sel_year}"
        sel_month = 0 
    elif sel_month > 0:
        _, num_days = calendar.monthrange(sel_year, sel_month)
        start_date = date(sel_year, sel_month, 1)
        end_date = date(sel_year, sel_month, num_days)
        filter_label = f"Månad {sel_month} ({sel_year})"
    else:
        start_date = date(sel_year, 1, 1)
        end_date = date(sel_year, 12, 31)
        filter_label = f"Hela År {sel_year}"
    start_str = start_date.strftime('%Y-%m-%d')
    end_str = end_date.strftime('%Y-%m-%d')
    shifts = Shift.query.filter(Shift.date >= start_str, Shift.date <= end_str).order_by(Shift.date, Shift.unit_id).all()
    vacancies = []
    total_shifts = len(shifts)
    filled_shifts = 0
    for shift in shifts:
        missing = []
        if not shift.amb_id: missing.append("AMB")
        if not shift.vub_id: missing.append("VUB")
        if missing:
            tid = shift.unit.day_time if shift.period == 'Dag' else (shift.unit.night_time if shift.period == 'Natt' else shift.unit.mid_time)
            vacancies.append({'date': shift.date, 'station': shift.unit.station.name, 'unit': shift.unit.name, 'period': shift.period, 'time': tid, 'missing': ", ".join(missing)})
        else: filled_shifts += 1
    fill_rate = int((filled_shifts / total_shifts * 100)) if total_shifts > 0 else 0
    return render_template('dashboard.html', users=users, stations=stations, vacancies=vacancies, fill_rate=fill_rate, vacancy_count=len(vacancies), sel_year=sel_year, sel_month=sel_month, sel_week=sel_week, filter_label=filter_label)

@app.route('/admin')
def admin(): return render_template('admin.html', stations=Station.query.all())
@app.route('/admin/add_user', methods=['POST'])
def add_user():
    db.session.add(User(name=request.form.get('name'), role=request.form.get('role'), home_station=request.form.get('home_station'), has_sits=True if request.form.get('has_sits') else False))
    db.session.commit()
    return redirect(url_for('dashboard'))
@app.route('/admin/delete_user/<int:user_id>')
def delete_user(user_id):
    db.session.delete(User.query.get(user_id))
    db.session.commit()
    return redirect(url_for('dashboard'))
@app.route('/admin/add_station', methods=['POST'])
def add_station():
    if not Station.query.filter_by(name=request.form.get('name')).first(): db.session.add(Station(name=request.form.get('name'))); db.session.commit()
    return redirect(url_for('admin'))
@app.route('/admin/update_station', methods=['POST'])
def update_station():
    s = Station.query.get(request.form.get('station_id'))
    if s: s.name = request.form.get('name'); db.session.commit()
    return redirect(url_for('admin'))
@app.route('/admin/update_unit', methods=['POST'])
def update_unit():
    u = Unit.query.get(request.form.get('unit_id'))
    if u:
        u.name = request.form.get('name'); u.day_time = request.form.get('day_time'); u.mid_time = request.form.get('mid_time'); u.night_time = request.form.get('night_time')
        u.requires_sits = bool(request.form.get('requires_sits')); u.is_flex = bool(request.form.get('is_flex')); db.session.commit()
    return redirect(url_for('admin'))
@app.route('/admin/export_excel')
def export_excel():
    data = [{'Datum': s.date, 'Station': s.unit.station.name, 'Enhet': s.unit.name, 'Period': s.period, 'Tid': s.unit.day_time if s.period=='Dag' else s.unit.night_time, 'AMB': s.amb.name if s.amb else '', 'VUB': s.vub.name if s.vub else ''} for s in Shift.query.all()]
    output = BytesIO(); pd.DataFrame(data).to_excel(output, index=False); output.seek(0)
    return send_file(output, download_name=f"Backup_{date.today()}.xlsx", as_attachment=True)
@app.route('/admin/import_excel', methods=['POST'])
def import_excel():
    try:
        df = pd.read_excel(request.files['file'])
        for _, row in df.iterrows():
            u = Unit.query.filter_by(name=row['Enhet']).first()
            if u:
                s = Shift.query.filter_by(date=str(row['Datum']).split(' ')[0], unit_id=u.id, period=row['Period']).first() or Shift(date=str(row['Datum']).split(' ')[0], unit_id=u.id, period=row['Period'])
                db.session.add(s)
                if pd.notna(row['AMB_Namn']): s.amb_id = (User.query.filter_by(name=str(row['AMB_Namn']).strip()).first() or s.amb_id).id if User.query.filter_by(name=str(row['AMB_Namn']).strip()).first() else None
                if pd.notna(row['VUB_Namn']): s.vub_id = (User.query.filter_by(name=str(row['VUB_Namn']).strip()).first() or s.vub_id).id if User.query.filter_by(name=str(row['VUB_Namn']).strip()).first() else None
        db.session.commit()
    except: pass
    return redirect(url_for('admin'))
@app.route('/admin/generate_template', methods=['POST'])
def generate_template():
    y, m = int(request.form.get('year')), int(request.form.get('month'))
    data = []
    for d in range(1, calendar.monthrange(y, m)[1] + 1):
        dt = date(y, m, d).strftime('%Y-%m-%d')
        for u in Unit.query.all():
            data.extend([{'Datum': dt, 'Station': u.station.name, 'Enhet': u.name, 'Period': p, 'Tid': u.day_time if p=='Dag' else (u.night_time if p=='Natt' else u.mid_time), 'AMB_Namn':'', 'VUB_Namn':''} for p in (['Dag', 'Mellan', 'Natt'] if u.mid_time else ['Dag', 'Natt'])])
    output = BytesIO(); pd.DataFrame(data).to_excel(output, index=False); output.seek(0)
    return send_file(output, download_name=f"Mall_{y}_{m}.xlsx", as_attachment=True)

if __name__ == "__main__":
    app.run(debug=True)