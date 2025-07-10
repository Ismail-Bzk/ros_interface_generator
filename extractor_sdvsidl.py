# ros_interface_generator/extractor_sdvsidl.py
import re
from typing import List, Tuple

def extract_topics_from_sdvsidl(filepath: str) -> List[str]:
    pattern = re.compile(r'topic_name:\s*"([\w\.]+)"')
    topics = []
    with open(filepath, 'r', encoding='utf-8') as f:
        for line in f:
            match = pattern.search(line)
            if match:
                topics.append(match.group(1))
    return topics

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
