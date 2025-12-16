# ros_interface_generator/msg_generator.py
import os
from pathlib import Path
import re
from typing import List, Tuple
from .utils import is_primitive_type, compute_topic_hint2, determine_ros_type_from_values, shorten_name_simple, extract_fixed_size_from_bytes_options, extract_primitive_byte_size__from_type,resolve_type, hint_to_acronym,occupied
from .proto_parser import find_message_block, find_enum_blocks, find_message_block_with_hint, find_proto_file_msg2



LOG_WARNINGS = []
LOG_WARNINGS_PATH = None

def log_warning(msg: str):
    LOG_WARNINGS.append(msg)
    if LOG_WARNINGS_PATH:
            os.makedirs(os.path.dirname(LOG_WARNINGS_PATH), exist_ok=True)
            with open(LOG_WARNINGS_PATH, "w", encoding="utf-8") as logf:
                logf.write("\n".join(LOG_WARNINGS))


def generate_enum_block(enum_name: str, block: str, field_name: str, max_line_length: int = 63) -> str:
    
    entries = re.findall(r'^\s*([A-Z0-9_]+)\s*=\s*(-?\d+)', block, re.MULTILINE)
    if not entries:
        log_warning(f"Warning: empty enum: {enum_name}")
        return f"Warning: empty enum: {enum_name}"
    
    values = [int(value) for _, value in entries]
    field_type = determine_ros_type_from_values(values)
    lines = [f"# Add Enum {enum_name}"]
    
    for name, value in entries:
        if '__' in name:
            name = name.replace('__', '_')
        
        short_name = shorten_name_simple(name,max_length=max_line_length)
        line = f"{field_type} C_{short_name} = {value}"
        if len(short_name) > max_line_length:
            log_warning(f"Error: generated line exceeds max length for enum : {enum_name}:\n {line}")
            return (f"Error: generated line exceeds max length for enum : {enum_name}:\n {line}")
        
        lines.append(line)
        
    return "\n".join(lines)


def resolve_output_filename_conflict(output_filename: str, topic_hint: str, generated_msgs: dict) -> Tuple[str, bool]:
    """
    Handle `.msg` filename conflicts based on the topic hint.

    Args:
        output_filename (str): Initial ROS filename without extension.
        topic_hint (str): Context hint for the message.
        generated_msgs (dict): Map of already generated files {ros_filename: topic_hint}.

    Returns:
        Tuple[str, bool]: (final `.msg` filename without extension, should_generate)
                          - should_generate == False → the file should be skipped
    """
    
    if output_filename in generated_msgs:
        previous_hint = generated_msgs[output_filename]
        if previous_hint == topic_hint:
            log_warning(
                f"Warning: message already generated: {output_filename}.msg with the same topic_hint → skipped"
                f"\n\t -> previous_hint: {previous_hint}\t -> topic_hint: {topic_hint}"
                )
            return output_filename, False
        else:
            # Conflict → rename using the topic_hint as a prefix
            hint_str = topic_hint.replace('.', '_')
            acro = hint_to_acronym(hint_str)  

            # Ensure uniqueness (avoid collisions)
            name = output_filename
            acro_up = acro
            name_up = name

            def _next_with_number(prefix: str, rest: str, topic_hint: str,
                                generated_msgs: dict[str, str] ,start: int = 2) -> str:
                """
                Find prefix{n}{rest} (n >= start) that doesn't collide with generated_msgs (for another topic)
                """
                i = start
                while True:
                    cand = f"{prefix}{i}{rest}"
                    if not occupied(cand, topic_hint, generated_msgs):
                        return cand
                    i += 1

            # If the name already starts with the acronym (HMISeatStatus...),
            # increment the acronym number to avoid HMIHMISeatStatus.
            if name_up.startswith(acro_up):
                # preserve the case of the existing name
                prefix = name[:len(acro)]       # "HMI"
                rest   = name[len(acro):]       # "SeatStatus..."
                # If the name is already HMI2SeatStatus, continue from 3
                m = re.match(rf'^({re.escape(prefix)})(\d+)(.*)$', name)
                if m:
                    prefix_no_num = m.group(1)  # "HMI"
                    current_num   = int(m.group(2))
                    rest          = m.group(3)
                    new_filename  = _next_with_number(prefix_no_num, rest, topic_hint, generated_msgs, start=current_num + 1)
                else:
                    new_filename  = _next_with_number(prefix, rest, topic_hint, generated_msgs, start=2)
            else:
                # Prepend the acronym; if collision, number the acronym
                prefix = acro                   # "HMI"
                rest   = name                   # "SeatStatus..."
                cand   = f"{prefix}{rest}"
                if occupied(cand, topic_hint, generated_msgs):
                    new_filename = _next_with_number(prefix, rest, topic_hint, generated_msgs, start=2)  # HMI2SeatStatus...
                else:
                    new_filename = cand

            if new_filename in generated_msgs:
                log_warning(
                    f"Warning: persistent conflict: {new_filename}.msg already exists even after rename → skipped"
                    f"\n\t -> previous_hint: {generated_msgs[new_filename]}\t -> topic_hint: {topic_hint}"
                )
                return new_filename, False
            else:
                log_warning(
                    f"Info: filename conflict detected for {output_filename}.msg → renaming to {new_filename}.msg"
                )
                return new_filename, True
    
    return output_filename, True


def generate_msg_type(attr_type: str, proto_dir: str, output_dir: str, generated_msgs: dict, topic_hint: str, ros_filename: str, event_name: str ,top_level: bool = False, manifest_records: list = None):

    global LOG_WARNINGS_PATH
    LOG_WARNINGS_PATH = os.path.join(output_dir, "generation_warnings.txt")
    
    base_type = attr_type.split('.')[-1]
    output_filename = ros_filename
    
    if topic_hint:
        block, proto_file = find_message_block_with_hint(proto_dir, base_type, topic_hint, top_level=top_level)
        if not block:
            block, proto_file = find_message_block(proto_dir, base_type)
    else:
        block, proto_file = find_message_block(proto_dir, base_type)
    
    if not block:
        log_warning(f"# Warning: message block not found for {base_type}")
        return

    output_filename, should_generate = resolve_output_filename_conflict(output_filename, topic_hint, generated_msgs)
    if not should_generate:
        return

    generated_msgs[output_filename] = topic_hint 
    output_path = os.path.join(output_dir, f"{output_filename}.msg")
    
    # Handle nested cases
    final_output_filename = output_filename
    final_output_path = output_path
    
    used_enums_in_file = set()  # Avoid duplicate enums
    
    with open(output_path, 'w', encoding='utf-8') as f:
        if top_level:
            f.write("ast_ssot_msgs/Header header\n")

        pattern = re.compile(r'^\s*(repeated\s+)?([\w\.]+)\s+([\w_]+)\s*=\s*\d+(?:\s*\[(.*?)\])?', re.MULTILINE | re.DOTALL)
        for match in pattern.finditer(block):
        
            is_repeated = match.group(1) is not None
            field_type = match.group(2)
            field_name = match.group(3)
            options_block = match.group(4) or ""

            repeated_count_match = re.search(r'\(.*repeated_field_max_count\)\s*=\s*(\d+)', options_block)
            suffix = f"[{repeated_count_match.group(1)}]" if repeated_count_match else "[]"

            if (len(field_name) > 63):
                log_warning(f"❌ Field name exceeds max length : {field_name} in {output_filename}.msg \t -> {shorten_name_simple(field_name, max_length=63)}")
                field_name = shorten_name_simple(field_name, max_length=63) # Comply with MATLAB-style rules
            
            if field_type == "bytes":
                if field_name=="raw_bytes":
                    log_warning(f"Warning: field {field_name} is inside a oneof block in {output_filename}.msg")
                    continue
                else:
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
                            type_enum = determine_ros_type_from_values(values)
                            if name.startswith(sub_base):
                                if name not in used_enums_in_file:
                                    f.write(f"{type_enum}{suffix if is_repeated else ''} {field_name}\n")
                                    enum_msg = generate_enum_block(name, enum_block, field_name)
                                    f.write(enum_msg + "\n")
                                    used_enums_in_file.add(name)
                                else:
                                    f.write(f"{type_enum}{suffix if is_repeated else ''} {field_name}  # Uses enum {name}\n")
                else:
                    hint_topic =  find_proto_file_msg2(proto_dir, sub_base, compute_topic_hint2(field_type), top_level=False)
                    hint_topic = hint_topic.split('.')[0]
                    output_type, should_gen = resolve_output_filename_conflict(sub_base, hint_topic, generated_msgs)
                    f.write(f"{output_type}{suffix if is_repeated else ''} {field_name}\n")
                    if should_gen:
                        generate_msg_type(sub_base, proto_dir, output_dir, generated_msgs, hint_topic, output_type, "", top_level=False,manifest_records=manifest_records)
                        if (sub_base == output_filename and hint_topic != topic_hint):
                            final_output_filename = hint_to_acronym(topic_hint) + output_filename
                            final_output_path = os.path.join(output_dir, f"{final_output_filename}.msg")
                            generated_msgs[output_filename] = topic_hint
    
    if Path(output_path).exists():
        Path(output_path).rename(final_output_path)
                            
    if manifest_records is not None:
        manifest_records.append({
            "ros_filename": f"{final_output_filename}.msg",
            "topic_name": attr_type,
            "event_name": event_name,
            "proto_file": topic_hint,
        })
    print(f"✔ Generated: {final_output_path}")
    
    if  LOG_WARNINGS:
        with open(LOG_WARNINGS_PATH, "w", encoding="utf-8") as logf:
            logf.write("\n".join(LOG_WARNINGS))
        print(f"Warnings written to  {LOG_WARNINGS_PATH}")