# ros_interface_generator/main.py
import os
from pathlib import Path
import argparse
from .utils import copy_header_msg, compute_topic_hint, parse_sdvsidl_file
from .extractor_sdvsidl import extract_topics_from_sdvsidl
from .msg_generator import generate_msg_type
from .srv_generator import write_srv_files
from .sanitizer import sanitize_ros_interfaces, parse_srv_and_generate_msgs


template_path = "D:/dev/sdv_adas_mainline/integration/mil_scripts/ros2_scripts/Templates/Header.msg"

def generate_all(sdvsidl_path: str, proto_dir: str, msg_output_dir: str, srv_output_dir: str):
    os.makedirs(msg_output_dir, exist_ok=True)
    #copy_header_msg(template_path, msg_output_dir)
    os.makedirs(srv_output_dir, exist_ok=True)
    generated_msgs = set()

    print("🔍 Extraction des topics...")
    topics = extract_topics_from_sdvsidl(sdvsidl_path)
    for topic in topics:
        suffix = topic.split(".")[-1]
        topic_hint = compute_topic_hint(topic)
        generate_msg_type(suffix, proto_dir, msg_output_dir, generated_msgs, topic_hint, top_level=True)

    print("🛠 Génération des fichiers .srv...")
    write_srv_files(sdvsidl_path, proto_dir, srv_output_dir)
    
    print("🛠 Génération des .msg manquants ...")
    parse_srv_and_generate_msgs(srv_output_dir, proto_dir, msg_output_dir)


    print("🧼 Sanitation des interfaces...")
    sanitize_ros_interfaces(msg_output_dir, srv_output_dir)

    print("✅ Fini ! Interfaces générées dans:")
    print(f"  - Messages : {msg_output_dir}")
    print(f"  - Services : {srv_output_dir}")

if __name__ == "__main__":
    
    if(0):
        parser = argparse.ArgumentParser(description="Générateur ROS2 à partir de .proto et .sdvsidl")
        parser.add_argument("--sdvsidl", required=True, help="Chemin vers le fichier .sdvsidl")
        parser.add_argument("--proto_dir", required=True, help="Répertoire contenant les fichiers .proto")
        parser.add_argument("--msg_output", required=True, help="Répertoire de sortie des .msg")
        parser.add_argument("--srv_output", required=True, help="Répertoire de sortie des .srv")
        args = parser.parse_args()

        generate_all(args.sdvsidl, args.proto_dir, args.msg_output, args.srv_output)


    projects = [
    "AebApp",
    "EmergencyBrakeSM",
    "ApoApp",
    "EgoVehicleCollector",
    "HmiManager",
    "IsaApp",
    "PathPlanner",
    "SceneUnderstanding",
    "PWTTorqueSM",
    "VehicleDynamicsSM",
    "TrajectoryController",
    "WorldModel",
    "CaccApp",
    "OccupantMonitor",
    "AccApp", #rust
    "AdasLocalAdapter", #rust
    ]
    sdvsidl_dir = "D:/dev/api/ampere/BL4.1/swc/adas" #"D:/dev/sdv_echassis_mainline/.ascii_packages/echassis_db/documentation/mbsw/sdvsidl/swc"
    proto_dir =  "D:/dev/api/ampere/catalog" #"D:/dev/sdv_echassis_mainline/.ascii_packages/echassis_db/documentation/mbsw/sdvsidl/catalog"
    output_base = Path(sdvsidl_dir).parents[-2]
    sdvsidl_files = parse_sdvsidl_file(sdvsidl_dir)
    for sdvsidl_file in sdvsidl_files:
            file_name_no_ext = Path(sdvsidl_file).stem
            if (file_name_no_ext in projects):
                msg_output_dir = output_base / "interfaces_comm"/ f"generated_msg_{file_name_no_ext}"
                srv_output_dir = output_base / "interfaces_comm" / f"generated_srv_{file_name_no_ext}"
                generate_all(sdvsidl_file, proto_dir, msg_output_dir, srv_output_dir)