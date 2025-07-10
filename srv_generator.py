# ros_interface_generator/srv_generator.py

import os
import re
from .extractor_sdvsidl import extract_rpc_methods_from_sdvsidl
from .proto_parser import find_message_block, find_service_block, find_enum_blocks
from .msg_generator import generate_msg_type, generate_enum_block
from .utils import is_primitive_type


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

                        if is_primitive_type(sub_type):
                            f.write(f"{sub_type}{array_suffix if is_repeated else ''} {sub_name}\n")
                        else:
                            sub_base = sub_type.split('.')[-1]
                            enum_matches = find_enum_blocks(proto_dir, sub_base)
                            if enum_matches:
                                for _, enums in enum_matches.items():
                                    for enum_name, block in enums:
                                        if enum_name.startswith(sub_base):
                                            enum_msg = generate_enum_block(enum_name, block, field_name=sub_name)
                                            f.write(enum_msg + "\n")
                                            break
                            else:
                                f.write(f"{sub_base}{array_suffix if is_repeated else ''} {sub_name}\n")
                    
                if type_str == input_type:
                    f.write("---\n")
        print(f"✔ .srv généré : {srv_path}")

