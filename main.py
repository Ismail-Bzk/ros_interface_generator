# ros_interface_generator/main.py
import os
import shutil
from pathlib import Path
import argparse
from .utils import copy_header_msg, parse_sdvsidl_file, write_manifest_json, json_to_csv, process_json_file, move_file, load_projects_filter, find_and_prefix_ros_filename_duplicates
from .extractor_sdvsidl import deduplicate_ros_filenames_by_topic_hint2,extract_topics_from_sdvsidl_file_list
from .msg_generator import generate_msg_type,LOG_WARNINGS
from .srv_generator import write_srv_files,LOG_SRV_WARNINGS
from .sanitizer import sanitize_ros_interfaces


# Global state
generated_msgs = dict()
manifest_records = []

# # List of allowed projects for the ABCD domains
PROJECTS_FILTER = []
PROJECTS_FILTER_SDVSIDL = []


def parse_and_sanitize(msg_output_dir, srv_output_dir, manifest_path: str):
    print("Sanitizing interfaces...")
    sanitize_ros_interfaces(msg_output_dir, srv_output_dir, manifest_path)
    print("Sanitizing Done ! Interfaces generated in:")
    print(f"  - Messages : {msg_output_dir}")
    print(f"  - Services : {srv_output_dir}")
    
    
def init_env(msg_output_dir: str, srv_output_dir: str, template_path: str = None):
    
    header_file = os.path.join(template_path, "Header.msg")
    futurama_projects = os.path.join(template_path, "project_fut.txt")
    os.makedirs(msg_output_dir, exist_ok=True)
    os.makedirs(srv_output_dir, exist_ok=True)
    
    if header_file and os.path.exists(header_file):
        copy_header_msg(header_file, msg_output_dir)
        
    if futurama_projects and os.path.exists(futurama_projects):
        print("futurama_projects file exists")
        PROJECTS_FILTER.extend(load_projects_filter(futurama_projects))
    
    
def generate_all2(proto_dir: str, msg_output_dir: str, srv_output_dir: str, projects_list: list):
    interfaces = extract_topics_from_sdvsidl_file_list(projects_list, proto_dir)
    interfaces_fixed = deduplicate_ros_filenames_by_topic_hint2(interfaces)
    
    for base_type, topic_hint, ros_filename, event in interfaces_fixed:
        print(f" base_type de {base_type} \t topic_hint '{topic_hint}' \t ros_filename  {ros_filename}.msg \t event_name {event}")

    for base_type, topic_hint, ros_filename, event_name in interfaces_fixed:
        generate_msg_type (
            base_type,              
            proto_dir, 
            msg_output_dir, 
            generated_msgs, 
            topic_hint.split('.')[0], 
            ros_filename, 
            event_name, 
            top_level=True,
            manifest_records=manifest_records)
        
    print("Generating .srv files...")
    if 0:
        for sdvsidl_file in projects_list:
            write_srv_files(sdvsidl_file, proto_dir, srv_output_dir, msg_output_dir, generated_msgs, manifest_records)

if __name__ == "__main__":
    
    if(1):
        parser = argparse.ArgumentParser(description="ROS2 generator from .proto and .sdvsidl")
        parser.add_argument("--sdvsidl", required=True, nargs="+",
                        help="Path(s) to one or more .sdvsidl folders/files")
        parser.add_argument("--proto_dir", required=True, help="Directory containing .proto files")
        parser.add_argument("--msg_output", required=True, help="Output directory for .msg files")
        parser.add_argument("--srv_output", required=True, help="Output directory for .srv files")
        parser.add_argument("--doc_output", required=True, help="Output directory for docs")
        parser.add_argument("--template", required=True, help="Path to a Header.msg")
        parser.add_argument(
            "--no_filter_projects",
            action="store_false",
            dest="filter_projects",
            help="Disable handling of projects listed in project_fut.txt (enabled by default)"
        )

        args = parser.parse_args()
        
        # Clean output folders
        for output_dir in [args.msg_output, args.srv_output, args.doc_output]:
            if os.path.exists(output_dir):
                shutil.rmtree(output_dir)
            os.makedirs(output_dir, exist_ok=True)
        
        # Initialize generation environment
        init_env(args.msg_output, args.srv_output, args.template)
        
        # Process provided sdvsidl files
        sdvsidl_files = []
        for sdvsidl_input in args.sdvsidl:
            domain = Path(sdvsidl_input).name
            print(f"\n===============================")
            print(f" Detected domain : {domain}")
            print(f" Scanned folder : {sdvsidl_input}")
            print("===============================\n")
            
            sdvsidl_files.extend(parse_sdvsidl_file(sdvsidl_input))
            print(f" sdvsidl Files found ({len(sdvsidl_files)}) : {[Path(f).stem for f in sdvsidl_files]}")

            if not args.filter_projects:
                print(f"\n All ABCD projects are considered (filter disabled)")
                PROJECTS_FILTER_SDVSIDL = sdvsidl_files 
            else:
                for sdvsidl_file in sdvsidl_files:
                    file_name_no_ext = Path(sdvsidl_file).stem
    
                    # Filter only the allowed projects
                    if file_name_no_ext in PROJECTS_FILTER:
                        PROJECTS_FILTER_SDVSIDL.append(sdvsidl_file)
        
        PROJECTS_FILTER_SDVSIDL = sorted(list(set(PROJECTS_FILTER_SDVSIDL)))
        print(f" Files included ({len(PROJECTS_FILTER_SDVSIDL)}) : {[Path(f).stem for f in PROJECTS_FILTER_SDVSIDL]}")
                
        generate_all2(args.proto_dir, args.msg_output, args.srv_output, PROJECTS_FILTER_SDVSIDL)  
        
        # Write  manifest JSON
        manifest_path = os.path.join(args.doc_output, "ros_interface_manifest.json")
        write_manifest_json(manifest_records, manifest_path)
        
        # Final Sanitation 
        parse_and_sanitize(args.msg_output, args.srv_output, manifest_path)
        
        # Post JSON  management
        find_and_prefix_ros_filename_duplicates(manifest_path,args.msg_output,True)
        process_json_file(manifest_path,manifest_path,manifest_path)

        # CSV generation
        json_to_csv(manifest_path, os.path.join(args.doc_output, "ros_interface_manifest.csv"))
        move_file(os.path.join(args.msg_output, "generation_warnings.txt"),os.path.join(args.doc_output, "generation_warnings.txt"))