# ros_interface_generator/msg_generator.py
import os
import re
from .utils import is_primitive_type, compute_topic_hint, copy_header_msg, determine_ros_type_from_values, shorten_name_simple, extract_fixed_size_from_bytes_options, extract_primitive_byte_size__from_type,resolve_type
from .proto_parser import find_message_block, find_enum_blocks, find_message_block_with_hint

def generate_enum_block(enum_name: str, block: str, field_name: str, max_line_length: int = 63) -> str:
    entries = re.findall(r'^\s*([A-Z0-9_]+)\s*=\s*(-?\d+)', block, re.MULTILINE)
    if not entries:
        return f"# ⚠ Empty enum: {enum_name}"
    
    values = [int(value) for _, value in entries]
    field_type = determine_ros_type_from_values(values)
    
    #lines = [f"{field_type} {field_name}", f"# Add Enum {enum_name}"]
    lines = [f"# Add Enum {enum_name}"]
    
    for name, value in entries:
        if '__' in name:
            name = name.replace('__', '_')
        
        short_name = shorten_name_simple(name,max_length=max_line_length)
        line = f"{field_type} C_{short_name} = {value}"
        if len(short_name) > max_line_length:
            return (f"# ❌ Ligne trop longue générée pour l'enum : {enum_name}:\n {line}")
        lines.append(line)
        
    return "\n".join(lines)

def generate_msg_type(attr_type: str, proto_dir: str, output_dir: str, generated_msgs: set, topic_hint, top_level: bool = False):
    base_type = attr_type.split('.')[-1]
    if base_type in generated_msgs:
        return

    if topic_hint:
        block = find_message_block_with_hint(proto_dir, base_type, topic_hint)
        if not block:
            block = find_message_block(proto_dir, base_type)
    else:
        block = find_message_block(proto_dir, base_type)
    if not block:
        return

    output_path = os.path.join(output_dir, f"{base_type}.msg")
    used_enums_in_file = set()  # ✅ Pour éviter les doublons
    
    with open(output_path, 'w', encoding='utf-8') as f:
        if top_level:
            f.write("swl_sdv_adas_msgs/Header header\n")

        pattern = re.compile(r'^\s*(repeated\s+)?([\w\.]+)\s+([\w_]+)\s*=\s*\d+(?:\s*\[(.*?)\])?', re.MULTILINE | re.DOTALL)
        for match in pattern.finditer(block):
            
            """repeated, field_type, field_name = match.groups()
            is_repeated = repeated is not None
            suffix = "[]" if is_repeated else "" """
            
            is_repeated = match.group(1) is not None
            field_type = match.group(2)
            field_name = match.group(3)
            options_block = match.group(4) or ""

            repeated_count_match = re.search(r'\(.*repeated_field_max_count\)\s*=\s*(\d+)', options_block)
            suffix = f"[{repeated_count_match.group(1)}]" if repeated_count_match else "[]"

            if field_type == "bytes":
                size = extract_fixed_size_from_bytes_options(options_block)
                if size:
                    f.write(f"uint8[{size}] {field_name}\n")
                else:
                    f.write(f"uint8 {field_name}\n")
                    
                    
                
                
            elif is_primitive_type(field_type):
                type_size = extract_primitive_byte_size__from_type(options_block)
                if( field_type.startswith("int") or field_type.startswith("uint")):
                    ros_type = resolve_type(field_type, type_size)
                    if ros_type:
                        f.write(f"{ros_type}{suffix if is_repeated else ''} {field_name}\n")
                    else:
                        f.write(f"{field_type}{suffix if is_repeated else ''} {field_name}\n")
                else:
                    f.write(f"{field_type}{suffix if is_repeated else ''} {field_name}\n")
                    
            else:
                sub_base = field_type.split('.')[-1]
                enums = find_enum_blocks(proto_dir, sub_base)
                if enums:
                    for _, enum_list in enums.items():
                        for name, enum_block in enum_list:
                            values = re.findall(r'=\s*(-?\d+)', enum_block)
                            values = [int(v) for v in values]
                            field_type = determine_ros_type_from_values(values)
                            
                            if name.startswith(sub_base):
                                if name not in used_enums_in_file:
                                    f.write(f"{field_type}{suffix if is_repeated else ''} {field_name}\n")
                                    enum_msg = generate_enum_block(name, enum_block, field_name)
                                    f.write(enum_msg + "\n")
                                    used_enums_in_file.add(name)
                                else:
                                    f.write(f"{field_type}{suffix if is_repeated else ''} {field_name}  # Uses enum {name}\n")
                else:
                    #f.write(f"{sub_base}{suffix} {field_name}\n")
                    f.write(f"{sub_base}{suffix if is_repeated else ''} {field_name}\n")
                    generate_msg_type(field_type, proto_dir, output_dir, generated_msgs,compute_topic_hint(field_type),top_level=False)

    generated_msgs.add(base_type)
    print(f"✔ Generated: {output_path}")
