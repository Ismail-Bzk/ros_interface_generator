# ros_interface_generator/srv_generator.py

import os
import re
from .extractor_sdvsidl import extract_rpc_methods_from_sdvsidl
from .proto_parser import find_message_block, find_service_block, find_enum_blocks
from .msg_generator import generate_msg_type, generate_enum_block
from .utils import is_primitive_type, determine_ros_type_from_values, shorten_name_simple, extract_fixed_size_from_bytes_options, extract_primitive_byte_size__from_type,resolve_type 


def extract_fields(block: str) -> list:
    """
    Extrait les champs d'un bloc message `.proto`.

    Returns:
        List[Tuple[str, str]]: Liste des tuples (type, nom_du_champ)
    """
    pattern = re.compile(
        r'^(repeated\s+)?([\w\.]+)\s+([\w_]+)\s*=\s*\d+(?:\s*\[.*?\])?',
        re.MULTILINE
    )
    fields = []
    for match in pattern.finditer(block):
        _, type_name, name = match.groups()
        fields.append((type_name, name))
    return fields


def write_srv_files(sdvsidl_path: str, proto_dir: str, output_dir: str):
    """
    Génère les fichiers .srv ROS2 à partir des définitions RPC dans le fichier `.sdvsidl`.

    Args:
        sdvsidl_path (str): Chemin vers le fichier `.sdvsidl`
        proto_dir (str): Répertoire contenant les fichiers `.proto`
        output_dir (str): Répertoire de sortie pour les `.srv`
        generated_msgs (set): Ensemble des types .msg déjà générés
    """
    field_pattern = re.compile(
        r'^\s*(repeated\s+)?([\w\.]+)\s+([\w_]+)\s*=\s*\d+(?:\s*\[(.*?)\])?',
        re.MULTILINE | re.DOTALL
    )
    os.makedirs(output_dir, exist_ok=True)
    methods = extract_rpc_methods_from_sdvsidl(sdvsidl_path)

    for service_full, method_name in methods:
        suffix = service_full.split('.')[-1]
        topic_hint = service_full.split('.')[-2] if '.' in service_full else ""

        input_type, output_type = find_service_block(proto_dir, method_name, suffix, topic_hint)
        if not input_type or not output_type:
            continue
        
        srv_path = os.path.join(output_dir, f"{method_name}.srv")
        used_enums_in_file = set()  # ✅ Pour éviter les doublons des enums
        
        with open(srv_path, 'w', encoding='utf-8') as f:
            for type_str in [input_type, output_type]:
                block = find_message_block(proto_dir, type_str)
                if block:
                    #fields = extract_fields_from_message_block(block)
                    for match in field_pattern.finditer(block):
                        is_repeated = match.group(1) is not None
                        sub_type = match.group(2)
                        sub_name = match.group(3)
                        options_block = match.group(4) or ""

                        repeated_count_match = re.search(r'\(.*repeated_field_max_count\)\s*=\s*(\d+)', options_block)
                        array_suffix = f"[{repeated_count_match.group(1)}]" if repeated_count_match else "[]"

                        if sub_type == "bytes":
                            size = extract_fixed_size_from_bytes_options(options_block)
                            if size:
                                f.write(f"uint8[{size}] {sub_name}\n")
                            else:
                                f.write(f"uint8 {sub_name}\n")
                    
                        elif is_primitive_type(sub_type):
                            type_size = extract_primitive_byte_size__from_type(options_block)
                            if( sub_type.startswith("int") or sub_type.startswith("uint")):
                                ros_type = resolve_type(sub_type, type_size)
                                if ros_type:
                                    f.write(f"{ros_type}{array_suffix if is_repeated else ''} {sub_name}\n")
                                else:
                                    f.write(f"{sub_type}{array_suffix if is_repeated else ''} {sub_name}\n")
                            else:
                                f.write(f"{sub_type}{array_suffix if is_repeated else ''} {sub_name}\n")
                            
                            #f.write(f"{sub_type}{array_suffix if is_repeated else ''} {sub_name}\n")
                        else:
                            sub_base = sub_type.split('.')[-1]
                            enums = find_enum_blocks(proto_dir, sub_base)
                            if enums:
                                for _, enum_list in enums.items():
                                    for name, enum_block in enum_list:
                                        values = re.findall(r'=\s*(-?\d+)', enum_block)
                                        values = [int(v) for v in values]
                                        field_type = determine_ros_type_from_values(values)
                                        
                                        if name.startswith(sub_base):
                                            if name not in used_enums_in_file:
                                                f.write(f"{field_type}{array_suffix if is_repeated else ''} {sub_name}\n")
                                                enum_msg = generate_enum_block(name, enum_block, field_name=sub_name)
                                                f.write(enum_msg + "\n")
                                                used_enums_in_file.add(name)
                                        else:
                                            
                                            f.write(f"{field_type}{array_suffix if is_repeated else ''} {sub_name}  # Uses enum {name}\n")
                                            
                            else:
                                f.write(f"{sub_base}{array_suffix if is_repeated else ''} {sub_name}\n")
                    
                if type_str == input_type:
                    f.write("---\n")
        print(f"✔ .srv généré : {srv_path}")

