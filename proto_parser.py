# ros_interface_generator/proto_parser.py
import os
import re
from typing import Optional, Dict, List, Tuple,Optional
from pathlib import Path
            
                        
def find_proto_file_msg2(proto_dir, message_name, topic_hint: str = "", top_level: bool = False):
    message_pattern = re.compile(r'\bmessage\s+' + re.escape(message_name) + r'\s*{')

    # Split the hint into segments: "sdv.chassis.stand_still_assist" -> ["sdv","chassis","stand_still_assist"]
    segments = [p for p in topic_hint.split('.') if p]

    def _has_pubsub(root: str) -> bool:
        # test by path segment
        return any(part == "pubsub" for part in Path(root).parts)

    def _search_with_hint(hint_subpath: str):
        """Traverse proto_dir applying top_level + path filtering by hint_subpath (if non-empty).
           Returns the matched .proto file, otherwise None.
        """
        for root, dirs, files in os.walk(proto_dir):
            dirs.sort()                 # deterministic traversal
            files = sorted(files)

            # Apply top_level filter on the path (by "pubsub" segment)
            for file in files:
                if not file.endswith(".proto"):
                    continue
                has_pub = _has_pubsub(root)
                if top_level and not has_pub:
                    continue
                if not top_level and has_pub:
                    continue

                path = os.path.join(root, file)

                # Filter by hint subpath (case-insensitive)
                if hint_subpath:
                    norm_path = Path(path).as_posix()
                    if hint_subpath not in norm_path:
                        continue

                # Read and search for the message
                try:
                    with open(path, 'r', encoding='utf-8') as f:
                        content = f.read()
                except Exception:
                    continue

                if message_pattern.search(content):
                    return file  

        return None

    # 1) Decreasing attempts: "sdv/chassis/stand_still_assist" -> "sdv/chassis" -> "sdv"
    for k in range(len(segments), 0, -1):
        sub = "/".join(segments[:k])
        res = _search_with_hint(sub)
        if res:
            return res

    # 2) Final attempt without hint (same top_level)
    res = _search_with_hint("")
    if res:
        return res

    # 3) Strategy fallback: if top_level=True, retry with top_level=False (using the same reduction logic)
    if top_level:
        return find_proto_file_msg2(proto_dir, message_name, topic_hint, top_level=False)

    # Not found
    return None

def find_message_block_with_hint(proto_dir, message_name, topic_hint="",top_level=False):
    message_pattern = re.compile(r'message\s+' + re.escape(message_name) + r'\s*{')
    for root, _, files in os.walk(proto_dir):
        for file in sorted(files):
            if file.endswith(".proto") and (not topic_hint or topic_hint in file) and (not top_level or 'topics' in file):

                path = os.path.join(root, file)
                try:
                    with open(path, 'r', encoding='utf-8') as f:
                        content = f.read()
                    match = message_pattern.search(content)
                    if match:
                        start_idx = match.start()
                        brace_count = 0
                        end_idx = start_idx
                        inside_message = False
                        while end_idx < len(content):
                            c = content[end_idx]
                            if c == '{':
                                brace_count += 1
                                inside_message = True
                            elif c == '}':
                                brace_count -= 1
                                if brace_count == 0 and inside_message:
                                    end_idx += 1
                                    break
                            end_idx += 1
                        return content[start_idx:end_idx],file
                except Exception:
                    continue
    return None,None


def find_message_block(proto_dir, message_name):
    message_pattern = re.compile(r'message\s+' + re.escape(message_name) + r'\s*{')
    for root, _, files in os.walk(proto_dir):
        for file in sorted(files):
            if file.endswith(".proto"):
                path = os.path.join(root, file)
                try:
                    with open(path, 'r', encoding='utf-8') as f:
                        content = f.read()
                    match = message_pattern.search(content)
                    if match:
                        start_idx = match.start()
                        brace_count = 0
                        end_idx = start_idx
                        inside_message = False
                        while end_idx < len(content):
                            c = content[end_idx]
                            if c == '{':
                                brace_count += 1
                                inside_message = True
                            elif c == '}':
                                brace_count -= 1
                                if brace_count == 0 and inside_message:
                                    end_idx += 1
                                    break
                            end_idx += 1
                        return content[start_idx:end_idx],file
                except (UnicodeDecodeError, OSError):
                    continue
    return None,None


def find_enum_blocks(proto_dir, base_type):
    enum_header_pattern = re.compile(r'enum\s+(' + re.escape(base_type) + r')\s*{')

    results = {}

    for root, _, files in os.walk(proto_dir):
        for file in sorted(files):
            if file.endswith(".proto"):
                path = os.path.join(root, file)
                try:
                    with open(path, 'r', encoding='utf-8') as f:
                        content = f.read()
                    matches = []
                    for match in enum_header_pattern.finditer(content):
                        enum_name = match.group(1)
                        start_idx = match.start()
                        brace_count = 0
                        end_idx = start_idx
                        inside_enum = False
                        while end_idx < len(content):
                            c = content[end_idx]
                            if c == '{':
                                brace_count += 1
                                inside_enum = True
                            elif c == '}':
                                brace_count -= 1
                                if brace_count == 0 and inside_enum:
                                    end_idx += 1
                                    break
                            end_idx += 1
                        enum_block = content[start_idx:end_idx]
                        matches.append((enum_name, enum_block))
                    if matches:
                        results[path] = matches
                        return results
                except (UnicodeDecodeError, OSError):
                    continue
    return None 


def find_service_block(proto_dir, method_name, service_name, topic_hint=""):
    method_pattern = re.compile(
        r'rpc\s+' + re.escape(method_name) + r'\s*\((.*?)\)\s+returns\s+\((.*?)\)', re.DOTALL
    )
    service_header_pattern = re.compile(r'service\s+' + re.escape(service_name) + r'\s*{')

    for root, _, files in os.walk(proto_dir):
        for file in sorted(files):
            if file.endswith(".proto") and (not topic_hint or topic_hint in file):
                path = os.path.join(root, file)
                try:
                    with open(path, 'r', encoding='utf-8') as f:
                        content = f.read()
                except Exception:
                    continue

                match = service_header_pattern.search(content)
                if match:
                    start_idx = match.end()  # start of the block after '{'
                    brace_count = 1
                    idx = start_idx

                    while idx < len(content) and brace_count > 0:
                        if content[idx] == '{':
                            brace_count += 1
                        elif content[idx] == '}':
                            brace_count -= 1
                        idx += 1

                    service_block = content[match.start():idx]
                    print(f"Service '{service_name}' found in {file}")

                    method_match = method_pattern.search(service_block)
                    if method_match:
                        request_type = method_match.group(1).strip()
                        response_type = method_match.group(2).strip()
                        print(f"    Method :  '{method_name}':")
                        print(f"        Input: {request_type}")
                        print(f"        Output: {response_type}")
                        return request_type, response_type
    return None, None