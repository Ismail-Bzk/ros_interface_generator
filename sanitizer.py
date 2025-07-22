# ros_interface_generator/sanitizer.py
import os
from pathlib import Path
from typing import List
import re
from .utils import PRIMITIVE_TYPES, remap_filename_to_ros_convention, is_primitive_type, compute_topic_hint
from .proto_parser import find_message_block
from .msg_generator import generate_msg_type

def parse_srv_and_generate_msgs(srv_dir: str, proto_dir: str, output_msg_dir: str) -> None:
    """
    Analyse tous les fichiers `.srv` pour générer les `.msg` manquants à partir des fichiers `.proto`.

    Args:
        srv_dir (str): Répertoire contenant les fichiers .srv
        proto_dir (str): Répertoire contenant les fichiers .proto
        output_msg_dir (str): Répertoire où générer les fichiers .msg
        generated_msgs (set): Ensemble des noms déjà générés
    """
    generated_msgs = set(os.listdir(output_msg_dir))  
    
    for srv_file in Path(srv_dir).glob("*.srv"):
        with srv_file.open("r", encoding="utf-8") as f:
            lines = f.readlines()

        for line in lines:
            line = line.strip()
            if not line or line.startswith("#") or line == "---":
                continue

            parts = line.split()
            if len(parts) != 2:
                continue

            type_str, _ = parts
            base_type = type_str.split(".")[-1]

            if is_primitive_type(base_type):
                continue

            msg_file = Path(output_msg_dir) / f"{base_type}.msg"
            if msg_file.exists():
                print(f"⚠ Déjà présent : {msg_file.name}")
                continue

            block = find_message_block(proto_dir, base_type)
            if not block:
                print(f"⚠ Bloc Introuvable dans les .proto : {base_type}")
                continue

            print(f"➕ Génération de {base_type}.msg")
            #generate_msg_type(base_type, proto_dir, output_msg_dir, generated_msgs, top_level=False)
            generate_msg_type(base_type, proto_dir, output_msg_dir, generated_msgs,compute_topic_hint(base_type),top_level=False)



def sanitize_interface_files(directory: str, extension: str) -> None:
    directory = Path(directory)
    rename_map = {}

    for file in directory.glob(f"*.{extension}"):
        original, corrected = remap_filename_to_ros_convention(file.stem)
        if original != corrected:
            rename_map[original] = corrected

    for file in directory.glob(f"*.{extension}"):
        path = file
        with path.open('r', encoding='utf-8') as f:
            lines = f.readlines()

        new_lines = []
        changed = False

        for line in lines:
            stripped = line.strip()
            #if not stripped or stripped.startswith("#") or "=" in stripped or stripped == "---":
            if not stripped or stripped.startswith("#") or "=" in stripped or "swl_sdv_adas_msgs" in stripped or "ssot_abcd" in stripped or stripped.startswith("builtin_interfaces") or stripped == "---":
                new_lines.append(line)
                continue

            tokens = stripped.split()
            if len(tokens) != 2:
                new_lines.append(line)
                continue

            type_name, field_name = tokens
            base_type = re.sub(r'\[.*\]', '', type_name)

            if base_type == "float":
                corrected_type = type_name.replace("float", "float32")
                new_lines.append(f"{corrected_type} {field_name}\n")
                changed = True
            elif base_type in PRIMITIVE_TYPES:
                new_lines.append(line)
            else:
                corrected_type = rename_map.get(base_type, remap_filename_to_ros_convention(base_type)[1])
                if corrected_type != base_type:
                    corrected_full = type_name.replace(base_type, corrected_type)
                    new_lines.append(f"{corrected_full} {field_name}\n")
                    changed = True
                else:
                    new_lines.append(line)

        if changed:
            with path.open('w', encoding='utf-8') as f:
                f.writelines(new_lines)
            print(f"✔ Contenu corrigé : {file}")

    for old_name, new_name in rename_map.items():
        old_path = directory / f"{old_name}.{extension}"
        new_path = directory / f"{new_name}.{extension}"
        if old_path.exists():
            old_path.rename(new_path)
            print(f"🔄 Fichier renommé : {old_name}.{extension} → {new_name}.{extension}")


def sanitize_ros_interfaces(msg_dir: str, srv_dir: str) -> None:
    sanitize_interface_files(msg_dir, "msg")
    sanitize_interface_files(srv_dir, "srv")