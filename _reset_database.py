from app import app
from database import db
from models import Station, Unit, User

with app.app_context():
    db.drop_all()
    db.create_all()
    print("Databas rensad och återskapad!")

    # 1. PERSONAL (Nu med has_c1)
    users = [
        User(name="Sven Svensson", role="VUB", has_sits=True, has_c1=True, home_station="Sollentuna"),
        User(name="Anna Andersson", role="AMB", has_sits=False, has_c1=True, home_station="Sollentuna"), # Har C1
        User(name="Lars Larsson", role="VUB", has_sits=False, has_c1=False, home_station="Norrtälje"),
        User(name="Karin Karlsson", role="AMB", has_sits=True, has_c1=False, home_station="Norrtälje"), # Saknar C1 (Testa boka henne på C1-bil!)
        User(name="Pool-Pelle", role="VUB", has_sits=False, has_c1=True, home_station="Pool"),
    ]
    db.session.add_all(users)
    db.session.commit()

    # 2. STATIONER & BILAR (Nu med requires_c1)
    # Format: ("Bilnamn", SITS, Flex, C1, "Dag", "Mellan", "Natt")
    data = {
        "Sollentuna": [
            ("335-9110", False, False, False, "07:00-19:00", "", "19:00-07:00"),
            ("335-9120", False, False, True, "07:30-19:30", "", "19:30-07:30"), # C1 KRAV!
            ("Flexbil - Sollentuna", False, True, False, "07:00-19:00", "", "Ej i drift")
        ],
        "Norrtälje": [
            ("334-9410", True, False, True, "07:30-19:30", "", "19:30-07:30"), # SITS + C1
            ("334-9420", True, False, False, "07:00-19:00", "", "19:00-07:00"),
            ("330-9100", False, False, False, "08:00-14:30", "", "Ej i drift")
        ],
        "FLEXBILAR (Övriga)": [
            ("FLEXBIL - Lindvreten", False, True, False, "07:30-16:30", "", "Ej i drift")
        ],
        "BLANKPASS / RESURS": [
            (f"Plats {i:02d}", False, False, False, "Enl. schema", "", "") for i in range(1, 21)
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
                requires_c1=u_data[3], # <--- C1
                day_time=u_data[4],
                mid_time=u_data[5],
                night_time=u_data[6]
            )
            db.session.add(unit)
    
    db.session.commit()
    print("Databas uppdaterad med C1-stöd!")