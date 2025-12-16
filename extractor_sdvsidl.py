# ros_interface_generator/extractor_sdvsidl.py
import re
from pathlib import Path
from typing import Optional, Dict, List, Tuple
from collections import defaultdict
from .utils import pascal_case, compute_topic_hint, compute_topic_hint2, hint_to_acronym
from .proto_parser import find_proto_file_msg2


EVENT_START_RE = re.compile(r'\bevent\b\s*{')
EVENT_NAME_RE  = re.compile(r'event_name:\s*"([^"]+)"')
TOPIC_NAME_RE  = re.compile(r'topic_name:\s*"([\w\.]+)(?:::(\w+))?"')
METHOD_START_RE  = re.compile(r'\bmethod_fire_forget\b\s*{')
METHOD_NAME_RE  = re.compile(r'method_name:\s*"([^"]+)"')

def extract_rpc_methods_from_sdvsidl(filepath: str) -> List[Tuple[str, str]]:
    results = []
    with open(filepath, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    inside_block = False
    brace_count = 0
    current_block = []

    for line in lines:
        if 'rpc_definition' in line and '{' in line:
            inside_block = True
            brace_count = line.count('{') - line.count('}')
            current_block = [line]
            continue

        if inside_block:
            current_block.append(line)
            brace_count += line.count('{') - line.count('}')
            if brace_count == 0:
                block_str = ''.join(current_block)
                service_match = re.search(r'rpc_service_name:\s*"([^"]+)"', block_str)
                service_name = service_match.group(1) if service_match else None
                method_matches = re.findall(r'method_vsidl_name:\s*"([^"]+)"', block_str)
                for method in method_matches:
                    if service_name:
                        results.append((service_name, method))
                inside_block = False
                current_block = []
    return results


def extract_topics_from_sdvsidl2(filepath: str,proto_dir) -> List[Tuple[str, str, str, Optional[str]]]:
    """
    Extract the interfaces to generate from a .sdvsidl file.

    Returns:
        List of (original_message_name, topic_hint, ros_filename, event_name)
    """
    interfaces: List[Tuple[str, str, str, Optional[str]]] = []

    with open(filepath, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    i = 0
    while i < len(lines):
        line = lines[i]

        # Start of an event block: event { ... }
        if EVENT_START_RE.search(line):
            brace = line.count('{') - line.count('}')
            block_lines = [line]
            i += 1
            while i < len(lines) and brace > 0:
                block_lines.append(lines[i])
                brace += lines[i].count('{') - lines[i].count('}')
                i += 1

            block = ''.join(block_lines)

            # Extract event_name from the block
            event_name_match = EVENT_NAME_RE.search(block)
            event_name = event_name_match.group(1) if event_name_match else None

            # Extract all topic_name entries inside this event block
            for m in TOPIC_NAME_RE.finditer(block):
                full_topic = m.group(1)        # ex: sdv.adas.hmi.ApplicationAccSettingRequest
                suffix     = m.group(2)        # ex: FIRST_ROW_LEFT ou None

                base_type  = full_topic.split('.')[-1]
                topic_hint = find_proto_file_msg2(proto_dir, base_type,compute_topic_hint2(full_topic),True) #compute_topic_hint(full_topic)
                ros_filename = f"{base_type}{pascal_case(suffix)}" if suffix else base_type

                interfaces.append((base_type, topic_hint, ros_filename, event_name))

            # continue the loop without i += 1 (already advanced while reading the block)
            continue

        # (fallback) If a topic_name appears outside an event block (unlikely),
        # collect it anyway with event_name=None
        tm = TOPIC_NAME_RE.search(line)
        if tm:
            full_topic = tm.group(1)
            suffix     = tm.group(2)
            base_type  = full_topic.split('.')[-1]
            topic_hint = find_proto_file_msg2(proto_dir, base_type,compute_topic_hint2(full_topic),True) #compute_topic_hint(full_topic)
            ros_filename = f"{base_type}{pascal_case(suffix)}" if suffix else base_type
            interfaces.append((base_type, topic_hint, ros_filename, None))

        i += 1

    return interfaces


def extract_topics_from_sdvsidl_file_list(file_list,proto_dir) -> List[Tuple[str, str, str, Optional[str]]]:
    all_interfaces = []
    for filepath in file_list:
        print(f"Extracting topics from {filepath} \n")
        
        interfaces = extract_topics_from_sdvsidl2(filepath,proto_dir)
        all_interfaces.extend(interfaces)
    return all_interfaces
        

def find_versioned_matches(
    interfaces: List[Tuple[str, str, str, Optional[str]]],
    same_topic: bool = True,
) -> List[str]:
    """
    Return the list of *versioned* ros_filename entries (…V1..V9)
    for which at least one other entry exists whose stem,
    after removing the V[1-9] suffix, is identical.
    - same_topic=True: limit the search to the same topic_hint
    - same_topic=False: search across all topics
    """
    ver_re = re.compile(r'(?i)V[1-9]$')  
    
    # Index variants by common base (stem without Vx)
    # key = (topic_hint, base_no_ver) if same_topic, else base_no_ver only
    def key(th: str, base_no_ver: str):
        return (th or "", base_no_ver) if same_topic else base_no_ver

    index = defaultdict(list)  # key -> [ros_filename...]
    for _, th, ros, _ in interfaces:
        stem = Path(ros).stem
        base_no_ver = ver_re.sub("", stem)
        index[key(th, base_no_ver)].append(ros)

    results: List[str] = []
    seen = set()

    # For each versioned entry, check if other variants share the same base_no_ver
    for _, th, ros, _ in interfaces:
        stem = Path(ros).stem
        if not ver_re.search(stem):
            continue  # only handle Vx-suffixed names

        base_no_ver = ver_re.sub("", stem)
        variants = index.get(key(th, base_no_ver), [])

        # Keep only if there is at least one OTHER entry (≠ itself)
        if any(v != ros for v in variants):
            if ros not in seen:
                results.append(ros)
                seen.add(ros)

    return results


def deduplicate_ros_filenames_by_topic_hint2(interfaces: List[Tuple[str, str, str, Optional[str]]]) -> List[Tuple[str, str, str, Optional[str]]]:
    """
    Modify ros_filename by adding the topic_hint when the same proto_message_name
    is used with multiple different topic_hints.

    Args:
        interfaces: List of tuples (proto_message_name, topic_hint, ros_filename)

    Returns:
        Updated list with disambiguated ros_filename values when needed.
    """
    
    # Versioned Vx entries that have matches
    versioned_conflicts = find_versioned_matches(interfaces, same_topic=False)
    print("🔎 Versioned duplicates detected:",
                  sorted(set(versioned_conflicts)))
    
    # Map {ros_filename: set(topic_hints)}
    hint_map = defaultdict(set)
    for base_type, topic_hint, ros_filename, event in interfaces:
        hint_map[ros_filename].add(topic_hint)

    # If a ros_filename is used in multiple contexts (different topic_hints)
    # → prepend the topic_hint acronym to the ros_filename
    updated = []
    for base_type, topic_hint, ros_filename, event in interfaces:
        new_ros_filename = ros_filename
        
        if len(hint_map[ros_filename]) > 1:
            topic_proto = topic_hint.split('.')[0]
            hint_str = topic_proto.replace('.', '_')
            new_ros_filename  = hint_to_acronym(hint_str) + ros_filename # pascal_case(hint_str) + ros_filename

        if ros_filename in versioned_conflicts:
            new_ros_filename = f"{ros_filename}XX"
            
        updated.append((base_type, topic_hint, new_ros_filename, event))
        
    return updated