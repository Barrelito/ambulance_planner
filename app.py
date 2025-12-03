import pandas as pd
import calendar
from io import BytesIO
from flask import Flask, render_template, request, redirect, url_for, send_file, flash, session
from database import db
from datetime import date, datetime, timedelta

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///ambulans.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.secret_key = 'hemlig'
SYSTEM_PASSWORD = "ambulans112"

db.init_app(app)
from models import *

def add_log(text):
    log_entry = AuditLog(action=text)
    db.session.add(log_entry)

@app.before_request
def require_login():
    allowed_routes = ['login', 'static']
    if request.endpoint not in allowed_routes and 'logged_in' not in session: return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        if request.form.get('password') == SYSTEM_PASSWORD: session['logged_in'] = True; return redirect(url_for('index'))
        else: flash("Fel lösenord.")
    return render_template('login.html')

@app.route('/logout')
def logout(): session.pop('logged_in', None); return redirect(url_for('login'))

@app.route('/')
def index():
    selected_date_str = request.args.get('date') or date.today().strftime('%Y-%m-%d')
    try: selected_date = datetime.strptime(selected_date_str, '%Y-%m-%d').date()
    except: selected_date = date.today(); selected_date_str = selected_date.strftime('%Y-%m-%d')
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
    vacant_spots = []
    all_units = Unit.query.all()
    for unit in all_units:
        if 'BLANKPASS' in unit.station.name: continue
        s_dag = shift_map.get(unit.id, {}).get('Dag')
        if not s_dag or not s_dag.amb_id or not s_dag.vub_id: vacant_spots.append({'id': unit.id, 'name': unit.name, 'period': 'Dag', 'station': unit.station.name})
        s_natt = shift_map.get(unit.id, {}).get('Natt')
        if not s_natt or not s_natt.amb_id or not s_natt.vub_id: vacant_spots.append({'id': unit.id, 'name': unit.name, 'period': 'Natt', 'station': unit.station.name})
        if unit.mid_time:
            s_mid = shift_map.get(unit.id, {}).get('Mellan')
            if not s_mid or not s_mid.amb_id or not s_mid.vub_id: vacant_spots.append({'id': unit.id, 'name': unit.name, 'period': 'Mellan', 'station': unit.station.name})
    return render_template('index.html', stations=all_stations, shift_map=shift_map, users=all_users, busy_users=busy_users, current_date=selected_date_str, prev_date=prev_date, next_date=next_date, vacant_spots=vacant_spots)

@app.route('/update_shift', methods=['POST'])
def update_shift():
    target_date = request.form.get('date'); unit_id = request.form.get('unit_id'); period = request.form.get('period')
    new_amb_id = int(request.form.get('amb_id')) if request.form.get('amb_id') else None
    new_vub_id = int(request.form.get('vub_id')) if request.form.get('vub_id') else None
    new_comment = request.form.get('comment')
    unit = Unit.query.get(unit_id)
    station_anchor = f"station-{unit.station.id}" if unit else ""
    def clear_from_blankpass(user_id):
        if not user_id: return
        user_shifts = Shift.query.filter_by(date=target_date, period=period).all()
        for s in user_shifts:
            if 'BLANKPASS' in s.unit.station.name:
                if s.amb_id == user_id: s.amb_id = None; add_log(f"Flyttade personal från {s.unit.name}")
                if s.vub_id == user_id: s.vub_id = None; add_log(f"Flyttade personal från {s.unit.name}")
    clear_from_blankpass(new_amb_id); clear_from_blankpass(new_vub_id)
    shift = Shift.query.filter_by(date=target_date, unit_id=unit_id, period=period).first()
    if not shift: shift = Shift(date=target_date, unit_id=unit_id, period=period); db.session.add(shift)
    log_messages = []
    if shift.amb_id != new_amb_id: log_messages.append("Ändrade AMB")
    if shift.vub_id != new_vub_id: log_messages.append("Ändrade VUB")
    if shift.comment != new_comment: log_messages.append("Ändrade kommentar")
    shift.amb_id = new_amb_id; shift.vub_id = new_vub_id; shift.comment = new_comment
    if log_messages: add_log(f"{target_date} | {unit.name}: {', '.join(log_messages)}")
    db.session.commit()
    return redirect(url_for('index', date=target_date, _anchor=station_anchor))

@app.route('/move_staff', methods=['POST'])
def move_staff():
    date_str = request.form.get('date'); person_id = int(request.form.get('person_id')); action = request.form.get('action') 
    person = User.query.get(person_id); person_name = person.name if person else "Okänd"
    old_shifts = Shift.query.filter_by(date=date_str).all()
    station_anchor = ""; old_unit_name = ""
    for s in old_shifts:
        if s.amb_id == person_id: s.amb_id = None; old_unit_name = s.unit.name
        if s.vub_id == person_id: s.vub_id = None; old_unit_name = s.unit.name
        if 'BLANKPASS' in s.unit.station.name: station_anchor = f"station-{s.unit.station.id}"
    if action == 'move':
        target_value = request.form.get('target_spot')
        if target_value:
            target_unit_id, target_period = target_value.split('|'); target_unit_id = int(target_unit_id)
            shift = Shift.query.filter_by(date=date_str, unit_id=target_unit_id, period=target_period).first()
            if not shift: shift = Shift(date=date_str, unit_id=target_unit_id, period=target_period); db.session.add(shift)
            if not shift.amb_id: shift.amb_id = person_id
            elif not shift.vub_id: shift.vub_id = person_id
            target_unit = Unit.query.get(target_unit_id); station_anchor = f"station-{target_unit.station.id}"
            add_log(f"{date_str}: Flyttade {person_name} från {old_unit_name} till {target_unit.name}")
    if action == 'delete': add_log(f"{date_str}: Tog bort {person_name} från {old_unit_name}"); flash("Personen har tagits bort.", "info")
    db.session.commit()
    return redirect(url_for('index', date=date_str, _anchor=station_anchor))

@app.route('/scheduler')
def scheduler():
    if 'logged_in' not in session: return redirect(url_for('login'))
    users = User.query.order_by(User.home_station, User.name).all(); stations = Station.query.all()
    return render_template('scheduler.html', users=users, stations=stations)

@app.route('/scheduler/generate', methods=['POST'])
def generate_schedule():
    if 'logged_in' not in session: return redirect(url_for('login'))
    user_id = int(request.form.get('user_id')); unit_id = int(request.form.get('unit_id'))
    start_date = datetime.strptime(request.form.get('start_date'), '%Y-%m-%d').date()
    total_weeks = int(request.form.get('total_weeks')); cycle_weeks = int(request.form.get('cycle_weeks'))
    user = User.query.get(user_id); unit = Unit.query.get(unit_id)
    pattern = []
    for w in range(1, cycle_weeks + 1):
        for d in range(1, 8): pattern.append(request.form.get(f"day_{w}_{d}"))
    for i in range(total_weeks * 7):
        current_date_str = (start_date + timedelta(days=i)).strftime('%Y-%m-%d')
        shift_type = pattern[i % len(pattern)]
        existing = Shift.query.filter_by(date=current_date_str).all()
        for s in existing:
            if s.amb_id == user_id: s.amb_id = None
            if s.vub_id == user_id: s.vub_id = None
        if shift_type == 'OFF': continue
        target_shift = Shift.query.filter_by(date=current_date_str, unit_id=unit_id, period=shift_type).first()
        if not target_shift: target_shift = Shift(date=current_date_str, unit_id=unit_id, period=shift_type); db.session.add(target_shift)
        if not target_shift.amb_id: target_shift.amb_id = user_id
        elif not target_shift.vub_id: target_shift.vub_id = user_id
        else: target_shift.vub_id = user_id
    add_log(f"Schemaläggaren: {user.name} -> {unit.name}"); db.session.commit(); flash(f"Schema genererat!", "success")
    return redirect(url_for('dashboard'))

@app.route('/admin/logs')
def view_logs():
    if 'logged_in' not in session: return redirect(url_for('login'))
    logs = AuditLog.query.order_by(AuditLog.timestamp.desc()).limit(100).all()
    return render_template('logs.html', logs=logs)

# --- DASHBOARD LOGIK MED FILTER ---
@app.route('/dashboard')
def dashboard():
    users = User.query.order_by(User.home_station, User.name).all()
    stations = Station.query.all()
    today = date.today()
    sel_year = request.args.get('year', type=int, default=today.year)
    sel_month = request.args.get('month', type=int, default=today.month)
    sel_week = request.args.get('week', type=int, default=0)
    sel_station_id = request.args.get('station_id', type=int, default=0)

    start_date, end_date, filter_label = None, None, ""
    if sel_week > 0:
        d = f"{sel_year}-W{sel_week}"
        start_date = datetime.strptime(d + '-1', "%Y-W%W-%w").date()
        end_date = start_date + timedelta(days=6)
        filter_label = f"Vecka {sel_week}, {sel_year}"; sel_month = 0 
    elif sel_month > 0:
        _, num_days = calendar.monthrange(sel_year, sel_month)
        start_date = date(sel_year, sel_month, 1); end_date = date(sel_year, sel_month, num_days)
        filter_label = f"Månad {sel_month} ({sel_year})"
    else: start_date = date(sel_year, 1, 1); end_date = date(sel_year, 12, 31); filter_label = f"Hela År {sel_year}"
    
    start_str = start_date.strftime('%Y-%m-%d'); end_str = end_date.strftime('%Y-%m-%d')
    existing_shifts = Shift.query.filter(Shift.date >= start_str, Shift.date <= end_str).all()
    shift_map = {}
    for s in existing_shifts: shift_map[(s.date, s.unit_id, s.period)] = s

    # FILTRERA ENHETER OM STATION ÄR VALD
    if sel_station_id > 0:
        all_units = Unit.query.filter_by(station_id=sel_station_id).all()
        selected_station_name = Station.query.get(sel_station_id).name
        filter_label += f" - {selected_station_name}"
    else:
        all_units = Unit.query.all()

    vacancies = []; total_potential_shifts = 0; filled_shifts = 0
    delta = end_date - start_date
    for i in range(delta.days + 1):
        d_str = (start_date + timedelta(days=i)).strftime('%Y-%m-%d')
        for unit in all_units:
            if 'BLANKPASS' in unit.station.name: continue
            periods = ['Dag', 'Natt']
            if unit.mid_time: periods.append('Mellan')
            for p in periods:
                total_potential_shifts += 1
                shift = shift_map.get((d_str, unit.id, p))
                missing = []
                if not shift: missing = ["AMB", "VUB"]
                else:
                    if not shift.amb_id: missing.append("AMB")
                    if not shift.vub_id: missing.append("VUB")
                if missing:
                    tid = unit.day_time if p == 'Dag' else (unit.night_time if p == 'Natt' else unit.mid_time)
                    vacancies.append({'date': d_str, 'station': unit.station.name, 'unit': unit.name, 'period': p, 'time': tid, 'missing': ", ".join(missing)})
                else: filled_shifts += 1
    
    fill_rate = int((filled_shifts / total_potential_shifts * 100)) if total_potential_shifts > 0 else 0
    vacancies = sorted(vacancies, key=lambda x: (x['date'], x['station']))
    
    return render_template('dashboard.html', users=users, stations=stations, vacancies=vacancies, fill_rate=fill_rate, vacancy_count=len(vacancies), 
                           sel_year=sel_year, sel_month=sel_month, sel_week=sel_week, sel_station_id=sel_station_id, filter_label=filter_label)

@app.route('/admin')
def admin(): return render_template('admin.html', stations=Station.query.all())
@app.route('/admin/add_user', methods=['POST'])
def add_user():
    db.session.add(User(name=request.form.get('name'), role=request.form.get('role'), home_station=request.form.get('home_station'), has_sits=bool(request.form.get('has_sits')))); db.session.commit()
    add_log(f"Lade till personal: {request.form.get('name')}"); return redirect(url_for('dashboard'))
@app.route('/admin/delete_user/<int:user_id>')
def delete_user(user_id): db.session.delete(User.query.get(user_id)); db.session.commit(); return redirect(url_for('dashboard'))
@app.route('/admin/add_station', methods=['POST'])
def add_station(): 
    if not Station.query.filter_by(name=request.form.get('name')).first(): db.session.add(Station(name=request.form.get('name'))); db.session.commit()
    return redirect(url_for('admin'))
@app.route('/admin/update_station', methods=['POST'])
def update_station(): s = Station.query.get(request.form.get('station_id')); s.name = request.form.get('name') if s else None; db.session.commit(); return redirect(url_for('admin'))
@app.route('/admin/update_unit', methods=['POST'])
def update_unit():
    u = Unit.query.get(request.form.get('unit_id'))
    if u:
        u.name=request.form.get('name'); u.day_time=request.form.get('day_time'); u.mid_time=request.form.get('mid_time'); u.night_time=request.form.get('night_time'); u.requires_sits=bool(request.form.get('requires_sits')); u.is_flex=bool(request.form.get('is_flex')); db.session.commit()
    return redirect(url_for('admin'))
@app.route('/admin/export_excel')
def export_excel():
    data = [{'Datum': s.date, 'Station': s.unit.station.name, 'Enhet': s.unit.name, 'Period': s.period, 'Tid': s.unit.day_time if s.period=='Dag' else s.unit.night_time, 'AMB_Namn': s.amb.name if s.amb else '', 'VUB_Namn': s.vub.name if s.vub else ''} for s in Shift.query.all()]
    output = BytesIO(); pd.DataFrame(data).to_excel(output, index=False); output.seek(0)
    return send_file(output, download_name=f"Backup_{date.today()}.xlsx", as_attachment=True)
@app.route('/admin/import_excel', methods=['POST'])
def import_excel():
    try:
        df = pd.read_excel(request.files['file']); missing_names = set()
        for _, row in df.iterrows():
            u = Unit.query.filter_by(name=row['Enhet']).first()
            if u:
                s = Shift.query.filter_by(date=str(row['Datum']).split(' ')[0], unit_id=u.id, period=row['Period']).first() or Shift(date=str(row['Datum']).split(' ')[0], unit_id=u.id, period=row['Period']); db.session.add(s)
                if pd.notna(row['AMB_Namn']): s.amb_id = (User.query.filter_by(name=str(row['AMB_Namn']).strip()).first() or s.amb_id).id if User.query.filter_by(name=str(row['AMB_Namn']).strip()).first() else None
                if pd.notna(row['VUB_Namn']): s.vub_id = (User.query.filter_by(name=str(row['VUB_Namn']).strip()).first() or s.vub_id).id if User.query.filter_by(name=str(row['VUB_Namn']).strip()).first() else None
        db.session.commit(); add_log("Importerade data från Excel")
    except: pass
    return redirect(url_for('admin'))
@app.route('/admin/generate_template', methods=['POST'])
def generate_template():
    y, m = int(request.form.get('year')), int(request.form.get('month')); data = []
    for d in range(1, calendar.monthrange(y, m)[1] + 1):
        dt = date(y, m, d).strftime('%Y-%m-%d')
        for u in Unit.query.all():
            data.extend([{'Datum': dt, 'Station': u.station.name, 'Enhet': u.name, 'Period': p, 'Tid': u.day_time if p=='Dag' else (u.night_time if p=='Natt' else u.mid_time), 'AMB_Namn':'', 'VUB_Namn':''} for p in (['Dag', 'Mellan', 'Natt'] if u.mid_time else ['Dag', 'Natt'])])
    output = BytesIO(); pd.DataFrame(data).to_excel(output, index=False); output.seek(0)
    return send_file(output, download_name=f"Mall_{y}_{m}.xlsx", as_attachment=True)

if __name__ == "__main__":

    # --- MIN SIDA & GNETA ---
@app.route('/my_view', methods=['GET'])
def my_view():
    # Vi behöver inloggning, men här fejkar vi den via dropdown i HTML
    # Om du hade riktig inloggning skulle vi använda session['user_id']
    
    all_users = User.query.order_by(User.name).all()
    user_id = request.args.get('user_id')
    
    my_shifts = []
    vacancies = []
    current_user = None

    if user_id:
        current_user = User.query.get(user_id)
        today_str = date.today().strftime('%Y-%m-%d')

        # 1. HÄMTA MINA PASS
        # Vi letar där jag är AMB eller VUB
        shifts = Shift.query.filter(
            ((Shift.amb_id == user_id) | (Shift.vub_id == user_id)),
            Shift.date >= today_str
        ).order_by(Shift.date).all()

        for s in shifts:
            # Hitta kollega
            colleague_name = None
            if s.amb_id == int(user_id):
                # Jag är AMB, vem är VUB?
                colleague_name = s.vub.name if s.vub else None
            else:
                # Jag är VUB, vem är AMB?
                colleague_name = s.amb.name if s.amb else None
            
            tid = s.unit.day_time if s.period == 'Dag' else (s.unit.night_time if s.period == 'Natt' else s.unit.mid_time)

            my_shifts.append({
                'date': s.date,
                'period': s.period,
                'station': s.unit.station.name,
                'unit': s.unit.name,
                'time': tid,
                'colleague': colleague_name,
                'comment': s.comment
            })

        # 2. HÄMTA LEDIGA PASS (GNETA)
        # Hämta alla pass framåt där min roll saknas
        # OBS: Detta hittar bara pass som REDAN FINNS i databasen (t.ex. någon har tagits bort).
        # Att generera alla teoretiska pass här blir tungt, vi börjar så här.
        
        potential_shifts = Shift.query.filter(Shift.date >= today_str).order_by(Shift.date).all()
        
        # Hämta mina intresseanmälningar för att se vad jag redan sökt
        my_interests = [i.shift_id for i in Interest.query.filter_by(user_id=user_id).all()]

        for s in potential_shifts:
            is_vacant = False
            
            # Om jag är AMB, kolla om AMB-platsen är tom
            if current_user.role == 'SSK' and s.amb_id is None:
                is_vacant = True
            
            # Om jag är VUB, kolla om VUB-platsen är tom
            if current_user.role == 'VUB' and s.vub_id is None:
                is_vacant = True
            
            if is_vacant:
                tid = s.unit.day_time if s.period == 'Dag' else (s.unit.night_time if s.period == 'Natt' else s.unit.mid_time)
                vacancies.append({
                    'id': s.id,
                    'date': s.date,
                    'period': s.period,
                    'station': s.unit.station.name,
                    'unit': s.unit.name,
                    'time': tid,
                    'has_applied': s.id in my_interests
                })

    return render_template('my_view.html', all_users=all_users, current_user=current_user, my_shifts=my_shifts, vacancies=vacancies)

@app.route('/apply_interest', methods=['POST'])
def apply_interest():
    user_id = request.form.get('user_id')
    shift_id = request.form.get('shift_id')
    
    # Kolla om redan ansökt
    existing = Interest.query.filter_by(user_id=user_id, shift_id=shift_id).first()
    if not existing:
        interest = Interest(user_id=user_id, shift_id=shift_id)
        db.session.add(interest)
        
        # Logga det
        u = User.query.get(user_id)
        s = Shift.query.get(shift_id)
        add_log(f"Intresseanmälan: {u.name} vill ha passet {s.date} på {s.unit.name}")
        
        db.session.commit()
        flash("Din intresseanmälan är registrerad!", "success")
        
    return redirect(url_for('my_view', user_id=user_id))
    
    app.run(debug=True)