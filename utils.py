import re
from typing import Tuple
import os
import shutil

PRIMITIVE_TYPES = {
    "bool", "byte", "char", "string",
    "float", "float32", "float64",
    "int8", "uint8", "int16", "uint16",
    "int32", "uint32", "int64", "uint64"
}



def to_snake_case(name: str) -> str:
    return re.sub(r'(?<!^)(?=[A-Z])', '_', name).lower()

def is_primitive_type(type_name: str) -> bool:
    return type_name.split('.')[-1] in PRIMITIVE_TYPES

def compute_topic_hint(topic_name: str) -> str:
    parts = topic_name.split('.')
    if len(parts) >= 4:
        return to_snake_case(parts[-2])
    if len(parts) == 3 and parts[1].lower() == "adas":
        return to_snake_case(parts[-1]).split('_')[0]
    return ""

def remap_filename_to_ros_convention(filename: str) -> Tuple[str, str]:
    # Supprimer l'extension si elle existe
    base = re.sub(r'\.(msg|srv)$', '', filename)
    original = base
    # Transformer "_t" ou "_T" final → ajouter un " T" pour forcer un token séparé
    base = re.sub(r'_t$', ' T', base, flags=re.IGNORECASE)
    # Identifier les mots/tokens
    tokens = re.findall(r'[A-Z]{2,}(?=[A-Z][a-z]|[0-9]|$)|[A-Z]?[a-z0-9]+|T', base)
    # Capitalize chaque token sauf s’il est tout en majuscule
    capitalized = [t[0].upper() + t[1:].lower() if not t.isupper() else t.capitalize() for t in tokens]
    transformed = ''.join(capitalized)
    # Ajout de DT si le fichier est un .msg/.srv et se termine par "Request"
    if transformed.endswith("Request"):
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