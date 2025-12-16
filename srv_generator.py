# ros_interface_generator/srv_generator.py

import os
import re
from .extractor_sdvsidl import extract_rpc_methods_from_sdvsidl
from .proto_parser import find_message_block, find_service_block, find_enum_blocks,find_proto_file_msg2
from .msg_generator import generate_msg_type, generate_enum_block,resolve_output_filename_conflict
from .utils import is_primitive_type,compute_topic_hint, compute_topic_hint2,  determine_ros_type_from_values, shorten_name_simple, extract_fixed_size_from_bytes_options, extract_primitive_byte_size__from_type,resolve_type



LOG_SRV_WARNINGS = []
LOG_WARNINGS_SRV_PATH = None

def log_warning(msg: str):
    LOG_SRV_WARNINGS.append(msg)
    if LOG_WARNINGS_SRV_PATH:
            os.makedirs(os.path.dirname(LOG_WARNINGS_SRV_PATH), exist_ok=True)
            with open(LOG_WARNINGS_SRV_PATH, "w", encoding="utf-8") as logf:
                logf.write("\n".join(LOG_SRV_WARNINGS))
    
    
def extract_fields(block: str) -> list:
    """
    Extract fields from a `.proto` message block.

    Returns:
        List[Tuple[str, str]]: List of tuples (type, field_name)
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


def write_srv_files(sdvsidl_path: str, proto_dir: str, output_dir: str, msg_dir : str,generated_msgs: dict,manifest_records: list = None):
    """
    Generate ROS2 `.srv` files from RPC definitions in the `.sdvsidl` file.

    Args:
        sdvsidl_path (str): Path to the `.sdvsidl` file
        proto_dir (str): Directory containing `.proto` files
        output_dir (str): Output directory for generated `.srv` files
        msg_dir (str): Directory where generated `.msg` files are written
        generated_msgs (dict): Map of already-generated `.msg` types (name : topic hint)
        manifest_records (list, optional): Collector for generation metadata

    """
    
    global LOG_WARNINGS_SRV_PATH
    LOG_WARNINGS_SRV_PATH = os.path.join(output_dir, "generation_warnings_srv.txt")
    
    field_pattern = re.compile(
        r'^\s*(repeated\s+)?([\w\.]+)\s+([\w_]+)\s*=\s*\d+(?:\s*\[(.*?)\])?',
        re.MULTILINE | re.DOTALL
    )
    os.makedirs(output_dir, exist_ok=True)
    methods = extract_rpc_methods_from_sdvsidl(sdvsidl_path)

    for service_full, method_name in methods:
        suffix = service_full.split('.')[-1]
        topic_hint = compute_topic_hint(service_full) # service_full.split('.')[-2] if '.' in service_full else ""

        input_type, output_type = find_service_block(proto_dir, method_name, suffix, topic_hint)
        if not input_type or not output_type:
            log_warning(f"Warning: service {method_name} could not be resolved from  {sdvsidl_path}.")
            continue
        
        srv_path = os.path.join(output_dir, f"{method_name}.srv")
        used_enums_in_file = set()  #To avoid duplicate enums
        
        with open(srv_path, 'w', encoding='utf-8') as f:
            for type_str in [input_type, output_type]:
                block, proto_file = find_message_block(proto_dir, type_str)
                if block:
                    for match in field_pattern.finditer(block):
                        is_repeated = match.group(1) is not None
                        sub_type = match.group(2)
                        sub_name = match.group(3)
                        options_block = match.group(4) or ""

                        repeated_count_match = re.search(r'\(.*repeated_field_max_count\)\s*=\s*(\d+)', options_block)
                        array_suffix = f"[{repeated_count_match.group(1)}]" if repeated_count_match else "[]"
                        
                        if (len(sub_name) > 63):
                            log_warning(f"Error: field name too long : {sub_name} in {method_name}.srv \t -> {shorten_name_simple(sub_name, max_length=63)}")
                            sub_name = shorten_name_simple(sub_name, max_length=63) # Comply with MATLAB-style rules

                        if sub_type == "bytes":
                            if sub_name=="raw_bytes":
                                log_warning(f"Warning: field {sub_name} is inside a oneof block in {method_name}.srv")
                                continue
                            else:
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
                                hint_topic = find_proto_file_msg2(proto_dir, sub_base, compute_topic_hint2(sub_type), top_level=False)
                                hint_topic = hint_topic.split('.')[0]
                                output_type, should_gen = resolve_output_filename_conflict(sub_base, hint_topic, generated_msgs)
                                f.write(f"{output_type}{array_suffix if is_repeated else ''} {sub_name}\n")
                                if  should_gen:
                                    #output_type, should_gen = resolve_output_filename_conflict(sub_base, compute_topic_hint(sub_type), generated_msgs)
                                    #generate_msg_type(sub_type, proto_dir, msg_dir, generated_msgs, compute_topic_hint(sub_type), output_type, "", top_level=False,manifest_records=manifest_records)
                                    generate_msg_type(sub_base, proto_dir, msg_dir, generated_msgs, hint_topic, output_type, "", top_level=False, manifest_records=manifest_records)
                                
                if type_str == input_type:
                    f.write("---\n")
        print(f"✔ Generated .srv : {srv_path}")

        if  LOG_SRV_WARNINGS:
            with open(LOG_WARNINGS_SRV_PATH, "w", encoding="utf-8") as logf:
                logf.write("\n".join(LOG_SRV_WARNINGS))
            print(f"Warnings written to  {LOG_WARNINGS_SRV_PATH}")