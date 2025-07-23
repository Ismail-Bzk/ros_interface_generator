import re
from typing import Tuple
import os
import shutil

PRIMITIVE_TYPES = {
    "bool", "char", "string",
    "float", "float32", "float64",
    "int8", "uint8", "int16", "uint16",
    "int32", "uint32", "int64", "uint64"
}

PBS_SIZE_MAP = {
    "PBS_ONE": 8,
    "PBS_TWO": 16,
    "PBS_FOUR": 32,
    "PBS_EIGHT": 64,
}

def resolve_type(base_type: str, pbs_value: str) -> str | None:
    if pbs_value not in PBS_SIZE_MAP:
        return None  

    size_in_bits = PBS_SIZE_MAP[pbs_value]

    
    if base_type.startswith("uint"):
        return f"uint{size_in_bits}"
    elif base_type.startswith("int"):
        return f"int{size_in_bits}"
    else:
        return None  # Type non pris en charge

def to_snake_case(name: str) -> str:
    return re.sub(r'(?<!^)(?=[A-Z])', '_', name).lower()

def is_primitive_type(type_name: str) -> bool:
    return type_name.split('.')[-1] in PRIMITIVE_TYPES

def compute_topic_hint(topic_name: str) -> str:
    parts = topic_name.split('.')
    if len(parts) >= 4:
        return to_snake_case("_".join(parts[1:-1]))

    if len(parts) == 3 and parts[1].lower() in ["adas",'chassis',"body"]:
        finalpart =  to_snake_case(parts[-1]).split('_')[0]
        return to_snake_case("_".join(parts[:-1])) + "_"+ finalpart
    return ""

def remap_filename_to_ros_convention(filename: str) -> Tuple[str, str]:
    # Supprimer l'extension si elle existe
    base = re.sub(r'\.(msg|srv)$', '', filename)
    original = base
    
    # Supprimer V suivi d'un chiffre s'il est à la fin du nom
    base = re.sub(r'V[0-9]$', '', base)
    
    # Transformer "_t" ou "_T" final → ajouter un " T" pour forcer un token séparé
    base = re.sub(r'_t$', ' T', base, flags=re.IGNORECASE)
    # Identifier les mots/tokens
    tokens = re.findall(r'[A-Z]{2,}(?=[A-Z][a-z]|[0-9]|$)|[A-Z]?[a-z0-9]+|[A-Z]|T', base)
    # Capitalize chaque token sauf s’il est tout en majuscule
    capitalized = [t[0].upper() + t[1:].lower() if not t.isupper() else t.capitalize() for t in tokens]
    transformed = ''.join(capitalized)
    # Ajout de DT si le fichier est un .msg/.srv et se termine par "Request" ou "Response"
    if transformed.endswith("Request") or transformed.endswith("Response") :
        transformed += "DT"
    return original, transformed

def copy_header_msg(template_path, output_dir):
    dest_path = os.path.join(output_dir, "Header.msg")
    if not os.path.exists(dest_path):
        shutil.copy(template_path, dest_path)
        print(f"✔ Copié : {dest_path}")
        
        
def parse_sdvsidl_file(sdvsidl_path):
    """
    return all sdvsidl files in the given path
    """
    sdvsidl_files = []
    for root, _, files in os.walk(sdvsidl_path):
        for file in files:
            if file.endswith('.sdvsidl'):
                sdvsidl_files.append(os.path.join(root, file))
    return sdvsidl_files


def determine_ros_type_from_values(values):
    """Détermine le type ROS approprié selon les valeurs de l'enum."""
    min_val = min(values)
    max_val = max(values)

    if min_val >= 0:
        if max_val <= 255:
            return 'uint8'
        elif max_val <= 65535:
            return 'uint16'
        else:
            return 'uint32'
    else:
        if min_val < -32768 or max_val > 32767:
            return 'int32'
        elif min_val < -128 or max_val > 127:
            return 'int16'
        else:
            return 'int8'

def shorten_name_simple(name, prefix='C_', max_length=64):
    """Raccourcit simplement le nom sans hash si trop long."""
    full_name = prefix + name
    if len(full_name) <= max_length:
        return name
    max_name_len = max_length - len(prefix)
    return name[:max_name_len]


def extract_fixed_size_from_bytes_options(options: str):
    match = re.search(r'\(.*variable_type_max_size\)\s*=\s*(\d+)', options)
    return int(match.group(1)) if match else None

def extract_primitive_byte_size__from_type(options: str):
    match = re.search(r'\(.*primitive_byte_size\)\s*=\s*(PBS_\w+)', options)
    return match.group(1) if match else None