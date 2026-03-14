import carla
import logging
import os
import glob
import re

DEFAULT_BLUEPRINTS = [
    "vehicle.audi.a2",
    "vehicle.nissan.micra",
    "vehicle.audi.tt",
    "vehicle.mercedes.coupe_2020",
    "vehicle.bmw.grandtourer",
    "vehicle.harley-davidson.low_rider",
    "vehicle.ford.ambulance",
    "vehicle.micro.microlino",
    "vehicle.carlamotors.firetruck",
    "vehicle.carlamotors.carlacola",
    "vehicle.carlamotors.european_hgv",
    "vehicle.ford.mustang",
    "vehicle.chevrolet.impala",
    "vehicle.lincoln.mkz_2020",
    "vehicle.citroen.c3",
    "vehicle.dodge.charger_police",
    "vehicle.nissan.patrol",
    "vehicle.jeep.wrangler_rubicon",
    "vehicle.mini.cooper_s",
    "vehicle.mercedes.coupe",
    "vehicle.dodge.charger_2020",
    "vehicle.ford.crown",
    "vehicle.seat.leon",
    "vehicle.toyota.prius",
    "vehicle.yamaha.yzf",
    "vehicle.kawasaki.ninja",
    "vehicle.bh.crossbike",
    "vehicle.mitsubishi.fusorosa",
    "vehicle.tesla.model3",
    "vehicle.gazelle.omafiets",
    "vehicle.tesla.cybertruck",
    "vehicle.diamondback.century",
    "vehicle.mercedes.sprinter",
    "vehicle.audi.etron",
    "vehicle.volkswagen.t2",
    "vehicle.lincoln.mkz_2017",
    "vehicle.dodge.charger_police_2020",
    "vehicle.vespa.zx125",
    "vehicle.mini.cooper_s_2021",
    "vehicle.nissan.patrol_2021",
    "vehicle.volkswagen.t2_2021"
]

def get_carla_blueprints(host='127.0.0.1', port=2000, timeout=2.0):
    try:
        client = carla.Client(host, port)
        client.set_timeout(timeout)
        world = client.get_world()
        blueprint_library = world.get_blueprint_library()
        vehicles = blueprint_library.filter('vehicle.*')
        blueprints = [vehicle.id for vehicle in vehicles]
        logging.info(f"Successfully retrieved {len(blueprints)} blueprints from CARLA.")
        return sorted(blueprints)
    except Exception as e:
        # logging.warning(f"Could not connect to CARLA to fetch blueprints ({e}). Using default list.")
        return DEFAULT_BLUEPRINTS

def get_carla_maps(root_dir=None):
    if root_dir is None:
        root_dir = os.getcwd()
        
    maps_dir = os.path.join(root_dir,  "maps")
    
    if not os.path.exists(maps_dir):
        logging.warning(f"Map directory not found: {maps_dir}")
        return []
        
    map_files = glob.glob(os.path.join(maps_dir, "*.xodr"))
    map_names = []
    
    for file_path in map_files:
        filename = os.path.basename(file_path)
        match = re.match(r"(.*)\.xodr$", filename)
        if match:
            map_names.append(match.group(1))
            
    return sorted(map_names)