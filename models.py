from database import db

class Station(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), nullable=False)
    units = db.relationship('Unit', backref='station', lazy=True)

class Unit(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(20), unique=True, nullable=False)
    station_id = db.Column(db.Integer, db.ForeignKey('station.id'), nullable=False)
    requires_sits = db.Column(db.Boolean, default=False)
    is_flex = db.Column(db.Boolean, default=False)
    day_time = db.Column(db.String(20), default="07:00-19:00")
    mid_time = db.Column(db.String(20), default="")
    night_time = db.Column(db.String(20), default="19:00-07:00") 

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    role = db.Column(db.String(20)) 
    has_sits = db.Column(db.Boolean, default=False)
    home_station = db.Column(db.String(50), default="Pool") 

class Shift(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.String(10), nullable=False) 
    period = db.Column(db.String(10), nullable=False) 
    
    unit_id = db.Column(db.Integer, db.ForeignKey('unit.id'), nullable=False)
    amb_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    vub_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    
    # --- NYTT FÄLT: KOMMENTAR ---
    comment = db.Column(db.String(250), nullable=True) 
    
    amb = db.relationship('User', foreign_keys=[amb_id])
    vub = db.relationship('User', foreign_keys=[vub_id])
    unit = db.relationship('Unit')