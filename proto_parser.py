# ros_interface_generator/proto_parser.py
import os
import re
from typing import Optional, Dict, List, Tuple

def find_message_block_with_hint(proto_dir, message_name, topic_hint=""):
    message_pattern = re.compile(r'message\s+' + re.escape(message_name) + r'\s*{')
    for root, _, files in os.walk(proto_dir):
        for file in files:
            if file.endswith(".proto") and (not topic_hint or topic_hint in file):
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
                        return content[start_idx:end_idx]
                except Exception:
                    continue
    return None


def find_message_block(proto_dir, message_name):
    message_pattern = re.compile(r'message\s+' + re.escape(message_name) + r'\s*{')
    for root, _, files in os.walk(proto_dir):
        for file in files:
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
                        return content[start_idx:end_idx]
                except (UnicodeDecodeError, OSError):
                    continue
    return None


def find_enum_blocks(proto_dir, base_type):
    enum_header_pattern = re.compile(r'enum\s+(' + re.escape(base_type) + r')\s*{')

    results = {}

    for root, _, files in os.walk(proto_dir):
        for file in files:
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
                except (UnicodeDecodeError, OSError):
                    continue
    return results


"""
find_service_block(proto_dir, method_name, service_name, topic_hint="") -> Tuple[str, str]:

    Recherche une méthode `rpc` à l’intérieur d’un service défini dans les fichiers `.proto`.

    La méthode est extraite uniquement si elle appartient bien à un service spécifique (ex: `HMIMgrAlertDisplayService`)
    contenu dans un fichier `.proto` correspondant à un contexte (`topic_hint`).

    Args:
        proto_dir (str): Dossier racine contenant les fichiers `.proto`.
        method_name (str): Nom de la méthode RPC à rechercher.
        service_name (str): Nom du service dans lequel la méthode doit apparaître.
        topic_hint (str, optional): Indice pour filtrer les fichiers `.proto` (ex: "hmi", "planning").

    Returns:
        Tuple[str, str]: Le type d’entrée et le type de sortie utilisés dans la méthode RPC (input_type, output_type),
"""
def find_service_block(proto_dir, method_name, service_name, topic_hint=""):
    method_pattern = re.compile(
        r'rpc\s+' + re.escape(method_name) + r'\s*\((.*?)\)\s+returns\s+\((.*?)\)', re.DOTALL
    )
    service_header_pattern = re.compile(r'service\s+' + re.escape(service_name) + r'\s*{')

    for root, _, files in os.walk(proto_dir):
        for file in files:
            if file.endswith(".proto") and (not topic_hint or topic_hint in file):
                path = os.path.join(root, file)
                try:
                    with open(path, 'r', encoding='utf-8') as f:
                        content = f.read()
                except Exception:
                    continue

                match = service_header_pattern.search(content)
                if match:
                    start_idx = match.end()  # début du bloc après '{'
                    brace_count = 1
                    idx = start_idx

                    while idx < len(content) and brace_count > 0:
                        if content[idx] == '{':
                            brace_count += 1
                        elif content[idx] == '}':
                            brace_count -= 1
                        idx += 1

                    service_block = content[match.start():idx]
                    print(f"✅ Service '{service_name}' trouvé dans {file}")

                    method_match = method_pattern.search(service_block)
                    if method_match:
                        request_type = method_match.group(1).strip()
                        response_type = method_match.group(2).strip()
                        print(f"    Méthode '{method_name}':")
                        print(f"        Input: {request_type}")
                        print(f"        Output: {response_type}")
                        return request_type, response_type
    return None, None


