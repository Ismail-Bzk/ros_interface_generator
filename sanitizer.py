# ros_interface_generator/sanitizer.py
import os
from pathlib import Path
from typing import List
import shutil
import re
import json
from .utils import PRIMITIVE_TYPES, remap_filename_to_ros_convention, is_primitive_type, compute_topic_hint, compute_topic_hint2, hint_to_acronym, load_prefixed_files_from_manifest,remap_fqin_to_ros_convention
from .proto_parser import find_message_block
from .msg_generator import generate_msg_type


def should_keep_line(line: str) -> bool:
    stripped = line.strip()

    if not stripped:
        return True

    skip_prefixes = ("#", "builtin_interfaces")
    skip_substrings = ("=", "swl_sdv_adas_msgs", "ssot_abcd","ast_ssot_msgs","ssot")
    skip_exact = ("---",)

    if stripped.startswith(skip_prefixes):
        return True
    if any(substr in stripped for substr in skip_substrings):
        return True
    if stripped in skip_exact:
        return True

    return False


def parse_srv_and_generate_msgs(srv_dir: str, proto_dir: str, output_msg_dir: str, manifest_records: list = None) -> None:
    """
    Analyze all `.srv` files to generate the missing `.msg` files from the `.proto` files.

    Args:
        srv_dir (str): Directory containing the .srv files
        proto_dir (str): Directory containing the .proto files
        output_msg_dir (str): Directory where the .msg files will be generated
        generated_msgs (set): Set of names already generated
        manifest_records (list): Optional list to collect generation metadata

    """ 
    generated_msgs = {}
    for file in Path(output_msg_dir).glob("*.msg"):
        generated_msgs[file.stem] = ""
    
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
                print(f"⚠ already present : {msg_file.name}")
                continue

            block, proto_file = find_message_block(proto_dir, base_type)
            if not block:
                print(f"⚠ Bloc unfound in .proto : {base_type}")
                continue

            print(f" Gen of {base_type}.msg")
            
            topic_hint = compute_topic_hint(type_str)
            ros_filename = base_type
            generate_msg_type(base_type, proto_dir, output_msg_dir, generated_msgs, topic_hint, ros_filename, "",top_level=False, manifest_records=manifest_records)



def sanitize_interface_files(directory: str, extension: str, manifest_path: str) -> None:
    directory = Path(directory)
    rename_map = {}

    # files to ignore because already "acro+topic_name"
    prefixed = load_prefixed_files_from_manifest(manifest_path)
    
    for file in sorted(directory.glob(f"*.{extension}")):
        
        if file.stem in prefixed:
            print(f" Ignored (contains an FQIN): {file.name}")
            original, corrected =  remap_fqin_to_ros_convention(file.stem)
            if original != corrected:
                rename_map[original] = corrected

        else :
            original, corrected = remap_filename_to_ros_convention(file.stem)
            if original != corrected:
                rename_map[original] = corrected

    for file in sorted(directory.glob(f"*.{extension}")):
        
        
        path = file
        with path.open('r', encoding='utf-8') as f:
            lines = f.readlines()

        new_lines = []
        changed = False

        for line in lines:
            stripped = line.strip()
            #if not stripped or stripped.startswith("#") or "=" in stripped or "swl_sdv_adas_msgs" in stripped or "ssot_abcd" in stripped or stripped.startswith("builtin_interfaces") or stripped == "---":
            if should_keep_line(line):
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
            elif base_type == "double":
                corrected_type = type_name.replace("double", "float64")
                new_lines.append(f"{corrected_type} {field_name}\n")
                changed = True
            elif base_type in PRIMITIVE_TYPES:
                new_lines.append(line)
            else:
                if(base_type in prefixed):
                    corrected_type = rename_map.get(base_type, remap_fqin_to_ros_convention(base_type)[1])
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
            print(f"✔ Content updated : {file}")

    for old_name, new_name in rename_map.items():
            #if old_name != new_name:
            old_path = directory / f"{old_name}.{extension}"
            new_path = directory / f"{new_name}.{extension}"
            if old_path.exists():
                old_path.rename(new_path)
                print(f"🔄 File renamed : {old_name}.{extension} → {new_name}.{extension}")
                """if not new_path.exists():
                    old_path.rename(new_path)
                    print(f"🔄 Fichier renommé : {old_name}.{extension} → {new_name}.{extension}")"""
                """else:
                    print(f"⚠️ Renommage ignoré : {new_name}.{extension} existe déjà. Conflit avec {old_name}.{extension}")
                    shutil.move(str(old_path), str(Path(directory).parents[0]/"conflicts") / f"{old_name}.{extension}")  # Déplacer vers un dossier de conflits
                    old_path.unlink()  #  Supprime l'ancien fichier"""


def sanitize_ros_interfaces(msg_dir: str, srv_dir: str, manifest_path: str) -> None:
    sanitize_interface_files(msg_dir, "msg", manifest_path)
    sanitize_interface_files(srv_dir, "srv", manifest_path)