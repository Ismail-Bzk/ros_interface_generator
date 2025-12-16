# ros_interface_generator/utils.py

import re
from typing import Tuple, Union, List, Dict
from collections import defaultdict

import os
import shutil
import json
import csv
from pathlib import Path

PRIMITIVE_TYPES = {
    "bool", "char", "string", "double",
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
        return None 


def move_file(src: str, dst: str):
    src_path=Path(src)
    dst_path= Path(dst)
    if src_path.exists() and src_path.is_file():
        shutil.move(str(src_path), str(dst_path))


def to_snake_case(name: str) -> str:
    return re.sub(r'(?<!^)(?=[A-Z])', '_', name).lower()


def pascal_case(s):
    """Converts a string to PascalCase by removing underscores and capitalizing each word."""
    return ''.join(part.capitalize() for part in s.lower().split('_'))


def hint_to_acronym(hint_str: str) -> str:
        parts = hint_str.split('_')
        return ''.join(part[0].upper() for part in parts if part)


def is_primitive_type(type_name: str) -> bool:
    return type_name.split('.')[-1] in PRIMITIVE_TYPES


def compute_topic_hint(topic_name: str) -> str:
    parts = topic_name.split('.')
    if len(parts) >= 4:
        return to_snake_case("_".join(parts[:-1]))

    if len(parts) == 3 and parts[1].lower() in ["adas",'chassis',"body"]:
        finalpart =  to_snake_case(parts[-1]).split('_')[0]
        return to_snake_case("_".join(parts[:-1])) 
    return ""


def compute_topic_hint2(topic_name: str) -> str:
    parts = topic_name.split('.')
    return (".".join(parts[:-1]))


def remap_fqin_to_ros_convention(filename: str) -> Tuple[str, str]:
     # Remove the extension if it exists
    base = re.sub(r'\.(msg|srv)$', '', filename)
    original = base
    
    # Do nothing if the name already ends with DT
    if base.endswith("DT"):
        return original, original
    
    # Remove V followed by a digit if it is at the end of the name
    base = re.sub(r'V[0-9]$', '', base)
    
    # Remove XX followed by a digit if it is at the end of the name
    base = re.sub(r'XX$', '', base)
    
    # Transform final "_t" or "_T" → add a " T" to force a separate token
    base = re.sub(r'_t$', ' T', base, flags=re.IGNORECASE)
    
    
    # Append DT if the file is a .msg/.srv and ends with "Request" or "Response"
    if base.endswith("Request") or base.endswith("Response") :
        base += "DT"
    
    if(len(base)>63):
        base =  base[-63:]
        base =  base[0].upper()+ base[1:]
        print(f"message {base} truncated to 63 characters")
        
    return original, base


def remap_filename_to_ros_convention(filename: str) -> Tuple[str, str]:
     # Remove the extension if it exists
    base = re.sub(r'\.(msg|srv)$', '', filename)
    original = base
    
    # Do nothing if the name already ends with DT
    if base.endswith("DT"):
        return original, original
    
    # Remove V followed by a digit if it is at the end of the name
    base = re.sub(r'V[0-9]$', '', base)
    
    # Remove XX followed by a digit if it is at the end of the name
    base = re.sub(r'XX$', '', base)
    
    # Transform final "_t" or "_T" → add a " T" to force a separate token
    base = re.sub(r'_t$', ' T', base, flags=re.IGNORECASE)
    
    
    # Identify words/tokens
    tokens = re.findall(r'[A-Z]{2,}(?=[A-Z][a-z]|[0-9]|$)|[A-Z]?[a-z0-9]+|[A-Z]|T', base)
    # Capitalize each token unless it is all uppercase
    capitalized = [t[0].upper() + t[1:].lower() if not t.isupper() else t for t in tokens]
    transformed = ''.join(capitalized)
    
    
    # Append DT if the file is a .msg/.srv and ends with "Request" or "Response"
    if transformed.endswith("Request") or transformed.endswith("Response") :
        transformed += "DT"
    
    if(len(transformed)>63):
        transformed =  transformed[-63:]
        transformed =  transformed[0].upper()+ transformed[1:]
        print(f"message {transformed} truncated to 63 characters")
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
    return sorted(sdvsidl_files)


def determine_ros_type_from_values(values):
    """Determines the ROS type based on the enum values."""
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


def shorten_name_simple(name, prefix='C_', max_length=63):
    """Return 'name' truncated as needed so that 'prefix + name' does not exceed 'max_length'."""
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


def load_prefixed_files_from_manifest(manifest_path: str) -> set[str]:
    """
    Load the manifest JSON and return the set of files already prefixed
    in the form fqin + topic_name.
    """
    with open(manifest_path, "r", encoding="utf-8") as f:
        manifest = json.load(f)

    prefixed_files = set()
    for rec in manifest:
        ros = rec.get("ros_filename", "")
        topic = rec.get("topic_name", "")
        proto_file = rec.get("proto_file", "")
        if not ros or not topic or not proto_file:
            continue

        fqin = hint_to_acronym(proto_file.replace(".", "_"))
        expected = f"{fqin}{topic}"
        if ros.startswith(expected) or (ros.startswith(fqin) and expected in ros):
            prefixed_files.add(Path(ros).stem)  # sans extension
    return prefixed_files


def write_manifest_json(records: list, output_path: str):
    """
    Write the list of generated interfaces to a human-readable JSON file.
    
    Args:
        records (list): List of dictionaries containing interface data.
        output_path (str): Path to the .json file to write.
    """
    try:
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(records, f, indent=2, ensure_ascii=False)
        
    except Exception as e:
        print(f"❌ Error while writing in the manifest JSON : {e}")


def apply_remap_on_json(json_data: List[Dict]) -> List[Dict]:
    """
    Apply remap_filename_to_ros_convention to each 'ros_filename'
    and update the field.
    """
    
    for entry in json_data:
        if "ros_filename" in entry:
            original, new_value = remap_filename_to_ros_convention(entry["ros_filename"])
            # keep the original extension
            ext = ".msg" if entry["ros_filename"].endswith(".msg") else ".srv"
            entry["ros_filename"] = new_value + ext
    return json_data


def apply_remap_on_json_using_manifest(json_data: List[Dict], manifest_path: str) -> List[Dict]:
    prefixed_files = load_prefixed_files_from_manifest(manifest_path)  # stems without extension

    for entry in json_data:
        ros = entry.get("ros_filename", "")
        if not ros:
            continue
        stem = Path(ros).stem
        ext  = ".msg" if ros.lower().endswith(".msg") else ".srv"

        if stem in prefixed_files:
            # already compliant (ACRO + topic_name) → do not remap
            _, new_value = remap_fqin_to_ros_convention(ros)
            entry["ros_filename"] = new_value + ext
        else:
            # standard remap 
            _, new_value = remap_filename_to_ros_convention(ros)
            entry["ros_filename"] = new_value + ext

    return json_data


def process_json_file(input_file: str, output_file: str, manifest_path: str):
    # Load JSON from a file
    with open(input_file, "r", encoding="utf-8") as f:
        data = json.load(f)
    
    # Apply the transformation
    updated = apply_remap_on_json_using_manifest(data, manifest_path)   #apply_remap_on_json(data)
    
    # Write the updated JSON to a new file
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(updated, f, indent=2, ensure_ascii=False)
    

def json_to_csv(
    input_data: Union[str, List[Dict]],
    output_file: Union[str, Path],
    encoding: str = "utf-8",
    indent: int = 2,
) -> Path:
    """
    Convert a JSON file or a Python list of dicts into a CSV file.

    Parameters
    ----------
    input_data : str | list[dict]
        Either a path to a JSON file or a Python object already loaded (list of dicts).
    output_file : str | Path
        Path where the CSV file will be written.
    encoding : str, optional
        Encoding for reading/writing files. Default is 'utf-8'.
    indent : int, optional
        JSON indent for error/debug printing if needed.

    Returns
    -------
    Path
        The path to the written CSV file.

    Raises
    ------
    ValueError
        If the input data is empty or not a list of dictionaries.
    """
    # Load the JSON if the Path is given
    if isinstance(input_data, (str, Path)):
        with open(input_data, "r", encoding=encoding) as f:
            data = json.load(f)
    else:
        data = input_data

    # minimal check
    if not data or not isinstance(data, list) or not isinstance(data[0], dict):
        raise ValueError("Input must be a non-empty list of dictionaries")

    # Convert into CSV
    output_file = Path(output_file)
    with output_file.open("w", newline="", encoding=encoding) as f:
        fieldnames = list(data[0].keys())
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(data)

    return output_file


def load_projects_filter(file_path: str | Path) -> list[str]:
    """
    Load the list of allowed projects from a text file.
    - 1 project per line
    - comments supported after '#'
    - empty lines are ignored
    - de-duplication while preserving order

    """
    p = Path(file_path)
    if not p.exists():
        print(f"Warning :  Projects File not found : {p} → PROJECTS_FILTER = []")
        return []

    items: list[str] = []
    seen = set()
    with p.open("r", encoding="utf-8") as f:
        for raw in f:
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            # remove inline comment
            if "#" in line:
                line = line.split("#", 1)[0].strip()
            if not line:
                continue
            if line not in seen:
                seen.add(line)
                items.append(line)
    return items


def find_and_prefix_ros_filename_duplicates(
    manifest_path: str,
    msg_output: str,
    save: bool = False,
) -> Tuple[Dict[str, List[str]], List[Tuple[str, str]]]:
    
    def _strip_ext(name: str) -> Tuple[str, str]:
        m = re.match(r"^(.*?)(\.(msg|srv))$", name, flags=re.IGNORECASE)
        return (m.group(1), m.group(2)) if m else (name, "")


    path = Path(manifest_path)
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)

    # 1) group (ros_filename, proto_file) by topic_name
    by_topic: Dict[str, List[Tuple[str, str]]] = defaultdict(list)
    for rec in data:
        topic = rec.get("topic_name", "")
        ros = rec.get("ros_filename", "")
        proto_file = rec.get("proto_file", "")
        if topic and ros:
            by_topic[topic].append((ros, proto_file))

    # 2) keep only those with duplicates AND at least one name compliant with  "ACRO(proto) + topic"
    def _has_at_least_one_acro_name(records: List[Tuple[str, str]], topic: str) -> bool:
        for ros, proto in records:
            stem, _ = _strip_ext(ros)
            acro = hint_to_acronym(proto)
            if stem == f"{acro}{topic}":
                return True
        return False
    
    duplicates: Dict[str, List[str]] = {
        topic: [ros for (ros, _) in records]
        for topic, records in by_topic.items()
        if len({ros for (ros, _) in records}) > 1
           and _has_at_least_one_acro_name(records, topic)
    }

    # 3) apply the FQIN prefix only for topics with duplicates
    changes: List[Tuple[str, str]] = []
    if duplicates:
        for rec in data:
            topic = rec.get("topic_name", "")
            proto_file = rec.get("proto_file", "")
            if topic not in duplicates:
                continue  # do not touch topics without duplicates

            ros = rec.get("ros_filename", "")
            if not ros:
                continue
            base, ext = _strip_ext(ros)

            # condition: base == topic_name
            if base == topic:
                new_ros = f"{hint_to_acronym(proto_file)}{base}{ext or '.msg'}"
                if new_ros != ros:
                    rec["ros_filename"] = new_ros
                    changes.append((ros, new_ros,proto_file))
                    
                    
                    if save and changes:
                        output_msg = os.path.join(msg_output, f"{ros}")
                        new_output_msg = os.path.join(msg_output, f"{new_ros}")
                        
                        if Path(new_output_msg).exists():
                            print(f"warning: target already exists, To skip rename: {ros} -> {new_ros}")

                            
                        if Path(output_msg).exists():
                            Path(output_msg).rename(new_output_msg)
                            print(f"file ros renamed from  {ros} --> {new_ros}")
                    

    # 4) save if requested
    if save and changes:
        with path.open("w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
            
            
def occupied(
    name: str,
    topic_hint: str,
    generated_msgs: dict[str, str],
) -> bool:
    """
    True if 'name' is already taken by another topic
    """
    if name in generated_msgs and generated_msgs[name] != topic_hint:
        return True
    return False