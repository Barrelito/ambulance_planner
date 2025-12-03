from app import app
from database import db
from models import Station, Unit, User

with app.app_context():
    db.drop_all()
    db.create_all()
    print("Databas rensad och återskapad!")

    # 1. PERSONAL (Nu med rätt roll: AMB)
    users = [
        User(name="Sven Svensson", role="VUB", has_sits=True, home_station="Sollentuna"),
        User(name="Anna Andersson", role="AMB", has_sits=False, home_station="Sollentuna"), # <-- ÄNDRAT
        User(name="Lars Larsson", role="VUB", has_sits=False, home_station="Norrtälje"),
        User(name="Karin Karlsson", role="AMB", has_sits=True, home_station="Norrtälje"),   # <-- ÄNDRAT
        User(name="Pool-Pelle", role="VUB", has_sits=False, home_station="Pool"),
    ]
    db.session.add_all(users)
    db.session.commit()

    # 2. STATIONER & BILAR
    data = {
        "Sollentuna": [
            ("335-9110", False, False, "07:00-19:00", "", "19:00-07:00"),
            ("335-9120", False, False, "07:30-19:30", "", "19:30-07:30"),
            ("Flexbil - Sollentuna", False, True, "07:00-19:00", "", "Ej i drift")
        ],
        "Upplands Väsby": [
            ("335-9210", False, False, "07:30-19:30", "", "19:30-07:30"),
            ("335-8210 (Dag)", False, False, "09:00-21:00", "", "Ej i drift"),
            ("335-8220 (Dag)", False, False, "09:00-17:00", "", "Ej i drift"),
            ("335-8610 (C1)", False, False, "11:00-22:00", "", "Ej i drift")
        ],
        "Sigtuna": [
            ("335-9310", False, False, "07:00-19:00", "", "19:00-07:00")
        ],
        "Järfälla": [
            ("335-9410", False, False, "07:15-19:15", "", "19:15-07:15"),
            ("335-8460", False, False, "06:50-15:00", "", "14:50-00:00") 
        ],
        "Upplands Bro": [
            ("335-9510", False, False, "07:15-19:15", "", "19:15-07:15")
        ],
        "Täby": [
            ("334-9110", False, False, "07:15-19:15", "", "19:15-07:15"),
            ("334-8110 (Dag)", False, False, "10:30-17:00", "", "Ej i drift"),
            ("334-8160 (Dag)", False, False, "10:00-21:00", "", "Ej i drift")
        ],
        "Vallentuna": [
            ("334-9210", False, False, "07:15-19:15", "", "19:15-07:15"),
            ("334-8260 (Dag)", False, False, "09:00-21:00", "", "Ej i drift"),
            ("Flexbil - Vallentuna", False, True, "07:15-19:00", "", "Ej i drift")
        ],
        "Åkersberga": [
            ("334-9310", True, False, "07:00-19:00", "", "19:00-07:00")
        ],
        "Norrtälje": [
            ("334-9410", True, False, "07:30-19:30", "", "19:30-07:30"),
            ("334-9420", True, False, "07:00-19:00", "", "19:00-07:00"),
            ("330-9100", False, False, "08:00-14:30", "", "Ej i drift")
        ],
        "Hallstavik": [
            ("334-9510", False, False, "08:00-20:00", "", "20:00-08:00")
        ],
        "Rimbo": [
            ("334-8660", False, False, "08:00-16:00", "", "16:00-00:00")
        ],
        "FLEXBILAR (Övriga)": [
            ("FLEXBIL - Lindvreten", False, True, "07:30-16:30", "", "Ej i drift")
        ],
        "BLANKPASS / RESURS": [
            (f"Plats {i:02d}", False, False, "Enl. schema", "", "") for i in range(1, 21)
        ]
    }

    for station_name, units in data.items():
        station = Station(name=station_name)
        db.session.add(station)
        db.session.commit()

        for u_data in units:
            unit = Unit(
                name=u_data[0], 
                station=station, 
                requires_sits=u_data[1], 
                is_flex=u_data[2],
                day_time=u_data[3],
                mid_time=u_data[4],
                night_time=u_data[5]
            )
            db.session.add(unit)
    
    db.session.commit()
    print("Databasen är uppdaterad med AMB/VUB!")