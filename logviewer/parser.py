import platform
import os
import re
import tarfile
import subprocess
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
import tempfile
import importlib.util
import logviewer
import traceback
import gzip
from concurrent.futures import ProcessPoolExecutor


def safe_parse(path):
        try:
            output_dir = f"{Path(path).stem}_log_analysis_results"
            if not os.path.exists(os.path.join(output_dir, "parsed_logs.json")):
                parse_bundle(path, output_dir)
            return {"path": path, "status": "Success", "output": output_dir}
        except Exception as e:
            return {"path": path, "status": "Error", "error": str(e)}
            
def parse_multiple_bundles(bundle_paths, workers=4):

    with ProcessPoolExecutor(max_workers=workers) as executor:
        results = list(executor.map(safe_parse, bundle_paths))

    return results
    
def find_readme():
    try:
        root = Path(logviewer.__file__).resolve().parent
        readme = root / "README.md"
        if readme.exists():
            return readme
    except Exception as e:
        print(f"❌ Could not locate README.md: {e}")
    return None

def parse_flat_boot_logs(member_extracted_dir, member_output_dir):
    for entry in os.listdir(member_extracted_dir):
        boot_path = os.path.join(member_extracted_dir, entry)
        if os.path.isdir(boot_path) and entry.startswith("boot"):
            print(f"🧠 Parsing VSF flat boot folder: {entry}")
            out_path = os.path.join(member_output_dir, "previous", entry)
            os.makedirs(out_path, exist_ok=True)

            logs = collect_event_logs(boot_path)
            logs.extend(collect_fastlog_entries(boot_path))
            logs.sort(key=lambda x: datetime.fromisoformat(x["timestamp"]))

            if not logs:
                print(f"⚠️ No logs parsed from {boot_path}")

            with open(os.path.join(out_path, "parsed_logs.json"), "w") as f:
                json.dump(logs, f, indent=2)

            collect_fastlogs(boot_path, out_path)
            
    
def parse_previous_boot_logs(bundle_dir, output_dir):
    prev_dir = os.path.join(bundle_dir, "previous_boot_logs")
    if not os.path.exists(prev_dir):
        return

    for entry in os.listdir(prev_dir):
        boot_path = os.path.join(prev_dir, entry)
        if os.path.isdir(boot_path) and entry.startswith("boot"):
            print(f"🔁 Parsing previous boot: {entry}")
            out_path = os.path.join(output_dir, "previous", entry)
            os.makedirs(out_path, exist_ok=True)

            logs = collect_event_logs(boot_path)
            logs.extend(collect_fastlog_entries(boot_path))
            logs.sort(key=lambda x: datetime.fromisoformat(x["timestamp"]))

            if not logs:
                print(f"⚠️ No logs parsed from {boot_path}")
                
            with open(os.path.join(out_path, "parsed_logs.json"), "w") as f:
                json.dump(logs, f, indent=2)

            collect_fastlogs(boot_path, out_path)

    
            
def parse_vsf_member(tar_path, member_output_dir):
    print(f"📦 Parsing VSF member bundle: {tar_path}")
    extracted = extract_bundle(tar_path, target_dir=member_output_dir + "_tmp")
    if not extracted:
        print(f"⚠️ Could not extract {tar_path}")
        return

    logs = collect_event_logs(extracted)
    logs.extend(collect_fastlog_entries(extracted))
    logs.sort(key=lambda x: datetime.fromisoformat(x["timestamp"]))

    fastlog_files = collect_fastlogs(extracted, member_output_dir)
    os.makedirs(member_output_dir, exist_ok=True)
    with open(os.path.join(member_output_dir, "parsed_logs.json"), "w") as f:
        json.dump(logs, f, indent=2)
    with open(os.path.join(member_output_dir, "fastlog_index.json"), "w") as f:
        json.dump(fastlog_files, f, indent=2)
    
    # Copy diagdump_*.txt to a /feature folder
    diag_dir = os.path.join(member_output_dir, "feature")
    os.makedirs(diag_dir, exist_ok=True)
    for root, _, files in os.walk(extracted):
        for file in files:
            if file.startswith("diagdump_") and file.endswith(".txt"):
                shutil.copy(os.path.join(root, file), os.path.join(diag_dir, file))

    parse_previous_boot_logs(extracted, member_output_dir)
    parse_flat_boot_logs(extracted, member_output_dir)
    
    try:
        shutil.rmtree(extracted)
    except Exception as e:
        print(f"⚠️ Failed to clean temp member dir {extracted}: {e}")
        
def get_fastlog_parser():
    root = Path(__file__).resolve().parent
    exec_name = "fastlogParser"
    system = platform.system()

    if system == "Linux":
        local_path = root / exec_name
        if not os.access(local_path, os.X_OK):
            temp_exec = Path(tempfile.gettempdir()) / exec_name
            if not temp_exec.exists():
                shutil.copy2(local_path, temp_exec)
                temp_exec.chmod(0o755)
            return str(temp_exec)
        return str(local_path)

    elif system == "Windows":
        local_path = Path(tempfile.gettempdir()) / exec_name
        if not local_path.exists():
            packaged_path = root / exec_name
            if not packaged_path.exists():
                raise FileNotFoundError(f"fastlogParser not found at {packaged_path}")
            shutil.copy2(packaged_path, local_path)

        # Convert path to WSL-compatible format
        drive, rest = os.path.splitdrive(str(local_path))
        if not drive or len(drive) < 2:
            raise ValueError(f"Invalid path for WSL conversion: {local_path}")
            
        rest_fixed = rest.replace("\\", "/")
        wsl_path = f"/mnt/{drive[0].lower()}{rest_fixed}"
        return ["wsl", wsl_path]

    raise RuntimeError(f"Unsupported platform: {system}")
    
def extract_bundle(path, target_dir=None):
    name = os.path.basename(path).replace(".tar.gz", "")
    tmp_dir = target_dir or os.path.join("tmp_extracted", name)
    os.makedirs(tmp_dir, exist_ok=True)
    try:
        with tarfile.open(path, "r:gz") as tar:
            tar.extractall(path=tmp_dir)
        return tmp_dir
    except Exception as e:
        print(f"❌ Failed to extract {path}: {e}")
        return None

def read_lines(path):
    if os.path.isdir(path):
        if platform.system() == "Windows":
            drive, rest = os.path.splitdrive(path)
            if not drive or len(drive) < 2:
                raise ValueError(f"Invalid path for WSL conversion: {local_path}")
            rest_fixed = rest.replace("\\", "/")
            wsl_path = f"/mnt/{drive[0].lower()}{rest_fixed}"
            journal_cmd = ["wsl", "journalctl", "-D", wsl_path, "--no-pager"]
        else:
            journal_cmd = ["journalctl", "-D", path, "--no-pager"]
        try:
            result = subprocess.run(journal_cmd, stdout=subprocess.PIPE, text=True)
            return result.stdout.splitlines()
        except Exception as e:
            print(f"⚠️ Failed to read journal logs from {path}: {e}")
            return []
    else:
        try:
            with open(path, "r", errors='ignore') as f:
                return f.readlines()
        except Exception as e:
            print(f"⚠️ Failed to read file {path}: {e}")
            return []


def parse_line(line):
    patterns = [
        re.compile(r'(?P<timestamp>\d{4}-\d{2}-\d{2}T[\d:.+\-]+)\s+(?P<hostname>\S+)\s+(?P<process>[^\[:]+)(?:\[(?P<pid>\d+)\])?:\s+Event\|(?P<event_id>\d+)\|(?P<severity>\S+)\|(?P<module>\S+)\|(?P<slot>[^|]*)\|(?P<message>.+)'),
        re.compile(r'(?P<timestamp>\d{4}-\d{2}-\d{2}T[\d:.+\-]+)\s+(?P<hostname>\S+)\s+(?P<process>[^\[:]+)(?:\[(?P<pid>\d+)\])?:\s+(?P<facility>\S+)\|(?P<severity>\S+)\|(?P<module>\S+)\|(?P<slot>[^|]*)\|(?P<submodule>[^|]*)\|(?P<source>[^|]*)\|(?P<message>.+)'),
        re.compile(r'(?P<timestamp>[A-Z][a-z]{2}\s+\d{1,2}\s+[\d:]{8})\s+(?P<hostname>\S+)\s+(?P<process>[^\[:]+)(?:\[(?P<pid>\d+)\])?:\s+(?P<message>.+)')
    ]
    for pattern in patterns:
        match = pattern.match(line.strip())
        if match:
            group = match.groupdict()
            try:
                if "T" in group["timestamp"]:
                    dt = datetime.fromisoformat(group["timestamp"])
                else:
                    dt = datetime.strptime(group["timestamp"], "%b %d %H:%M:%S").replace(year=datetime.now().year)
                group["timestamp"] = dt.astimezone(timezone.utc).isoformat()
            except Exception as e:
                print(f"⚠️ Failed to parse timestamp: {group.get('timestamp')} - {e}")
                return None
            return group
    return None


def collect_event_logs(bundle_dir):
    logs = []
    for root, _, files in os.walk(bundle_dir):
        for file in files:
            full_path = os.path.join(root, file)

            # Handle compressed .gz log files
            if file.endswith(".gz"):
                try:
                    with gzip.open(full_path, "rt", errors='ignore') as f:
                        for line in f:
                            entry = parse_line(line)
                            if entry:
                                entry["source"] = "eventlog"
                                logs.append(entry)
                except Exception as e:
                    print(f"⚠️ Failed to parse compressed log {file}: {e}")
                continue

            # Handle normal .log and journal files
            if file.endswith(".log") or "journal" in file:
                for line in read_lines(full_path):
                    entry = parse_line(line)
                    if entry:
                        entry["source"] = "eventlog"
                        logs.append(entry)

    return logs

def translate_path_for_wsl(path):
    abs_path = os.path.abspath(path)
    drive, rest = os.path.splitdrive(abs_path)
    if not drive or len(drive) < 2:
        raise ValueError(f"Invalid path for WSL translation: '{path}'")
    rest_fixed = rest.replace("\\", "/")
    return f"/mnt/{drive[0].lower()}{rest_fixed}"

def collect_fastlogs(bundle_dir, output_dir):
    fastlog_cmd = get_fastlog_parser()
    fastlog_files = []
    fastlog_output_dir = os.path.join(output_dir, "fastlogs")
    os.makedirs(fastlog_output_dir, exist_ok=True)
    for root, _, files in os.walk(bundle_dir):
        for fname in files:
            if fname.endswith(".supportlog"):
                full_path = os.path.join(root, fname)
                if isinstance(fastlog_cmd, list):
                    ## print(f"🪵 Translating to WSL: {full_path}")
                    input_path = translate_path_for_wsl(full_path)
                    ## print(f"✅ Translated: {input_path}")
                    cmd = fastlog_cmd + ["-v", input_path]
                else:
                    cmd = [fastlog_cmd, "-v", full_path]
                try:
                    ## print(f"📦 Running command: {' '.join(cmd)}")
                    result = subprocess.run(cmd, stdout=subprocess.PIPE, text=True)
                    out_file = os.path.join(fastlog_output_dir, fname + ".txt")
                    with open(out_file, "w") as f:
                        f.write(result.stdout)
                    fastlog_files.append(fname + ".txt")
                except Exception as e:
                    traceback.print_exc()
                    print(f"⚠️ Failed to parse {fname}: {e}")
    return fastlog_files

def collect_fastlog_entries(bundle_dir):
    fastlog_cmd = get_fastlog_parser()
    entries = []
    for root, _, files in os.walk(bundle_dir):
        for fname in files:
            if fname.endswith(".supportlog"):
                full_path = os.path.join(root, fname)
                process_name = os.path.basename(fname).replace(".supportlog", "")
                if isinstance(fastlog_cmd, list):
                    ## print(f"🪵 Translating to WSL: {full_path}")
                    input_path = translate_path_for_wsl(full_path)
                    ## print(f"✅ Translated: {input_path}")
                    cmd = fastlog_cmd + ["-v", input_path]
                else:
                    cmd = [fastlog_cmd, "-v", full_path]
                try:
                    ## print(f"📦 Running command: {' '.join(cmd)}")
                    result = subprocess.run(cmd, stdout=subprocess.PIPE, text=True)
                    lines = result.stdout.splitlines()
                    buffer = []
                    timestamp = None
                    for line in lines:
                        if re.match(r"\(\d{2} \w{3} \d{2} \d{2}:\d{2}:\d{2}\.\d+", line):
                            if buffer and timestamp:
                                entries.append({
                                    "timestamp": timestamp,
                                    "process": process_name,
                                    "message": "\n".join(buffer),
                                    "source": "fastlog"
                                })
                            buffer = [line.strip()]
                            match = re.match(r"\((?P<ts>\d{2} \w{3} \d{2} \d{2}:\d{2}:\d{2}\.\d+)", line)
                            try:
                                raw_ts = match.group("ts")
                                truncated_ts = re.sub(r'\.(\d{6})\d+', r'.\1', raw_ts)
                                dt = datetime.strptime(truncated_ts, "%d %b %y %H:%M:%S.%f")
                                timestamp = dt.astimezone(timezone.utc).isoformat()
                            except Exception as e:
                                print(f"⚠️ Failed to parse fastlog timestamp in {fname}: {line.strip()} - {e}")
                                timestamp = None
                                buffer = []
                        else:
                            if buffer is not None:
                                buffer.append(line.strip())
                    if buffer and timestamp:
                        entries.append({
                            "timestamp": timestamp,
                            "process": process_name,
                            "message": "\n".join(buffer),
                            "source": "fastlog"
                        })
                except Exception as e:
                    traceback.print_exc()
                    print(f"⚠️ Failed to extract fastlog entries from {fname}: {e}")
    return entries

def collect_showtech_and_diag(bundle_dir):
    showtech = None
    diag = {}
    isp = None
    for root, _, files in os.walk(bundle_dir):
        for file in files:
            if file == "showtech.txt":
                showtech = os.path.join(root, file)
            elif file == "isp.txt":
                isp = os.path.join(root, file)
            elif file == "diagdump.txt" and "feature" in root:
                rel_dir = os.path.relpath(root, bundle_dir)
                diag[rel_dir] = os.path.join(root, file)
    return showtech, diag, isp

def split_showtech(showtech_path, output_dir):
    sections = {}
    current = None
    buffer = []

    showtech_dir = os.path.join(output_dir, "showtech")
    os.makedirs(showtech_dir, exist_ok=True)

    def flush():
        if current and buffer:
            fname = f"showtech_{current.replace(' ', '_').replace('/', '_')}.txt"
            full_path = os.path.join(showtech_dir, fname)
            with open(full_path, "w") as f:
                f.writelines(buffer)
            sections[current] = os.path.join("showtech", fname)

    with open(showtech_path, "r", errors='ignore') as f:
        for line in f:
            match = re.search(r'Command\s*:\s*show (.+)', line)
            if match:
                flush()
                current = f"show {match.group(1).strip()}"
                buffer = [line]
            elif current:
                buffer.append(line)
    flush()
    return sections

def save_text_file_summary(input_path, out_path):
    try:
        with open(input_path, 'r', errors='ignore') as f:
            content = f.read()
        with open(out_path, 'w') as out:
            out.write(content)
    except Exception as e:
        print(f" Failed to process {input_path}: {e}")

def parse_bundle(bundle_path, output_dir):
    os.makedirs(output_dir, exist_ok=True)
    bundle_dir = extract_bundle(bundle_path)
    if not bundle_dir:
        return None

    logs = collect_event_logs(bundle_dir)
    logs.extend(collect_fastlog_entries(bundle_dir))
    logs.sort(key=lambda x: datetime.fromisoformat(x["timestamp"]))

    fastlog_files = collect_fastlogs(bundle_dir, output_dir)
    with open(os.path.join(output_dir, "parsed_logs.json"), "w") as f:
        json.dump(logs, f, indent=2)
    with open(os.path.join(output_dir, "fastlog_index.json"), "w") as f:
        json.dump(fastlog_files, f, indent=2)

    showtech_path, diag_dumps, isp_file = collect_showtech_and_diag(bundle_dir)
    if isp_file:
        shutil.copy(isp_file, os.path.join(output_dir, "isp.txt"))
    if showtech_path:
        index = split_showtech(showtech_path, output_dir)
        with open(os.path.join(output_dir, "showtech_index.json"), "w") as f:
            json.dump(index, f, indent=2)

    diag_dir = os.path.join(output_dir, "feature")
    os.makedirs(diag_dir, exist_ok=True)
    for name, path in diag_dumps.items():
        out_name = name.replace(os.sep, "_") + "_diagdump.txt"
        full_path = os.path.join(diag_dir, out_name)
        save_text_file_summary(path, full_path)
    with open(os.path.join(output_dir, "diag_index.json"), "w") as f:
        json.dump(list(diag_dumps.keys()), f, indent=2)

    # Check for VSF member bundles
    members_dir = os.path.join(output_dir, "members")
    os.makedirs(members_dir, exist_ok=True)
    for root, _, files in os.walk(bundle_dir):
        for file in files:
            if re.match(r"mem_\d+_support_files\.tar\.gz", file):
                member_tar = os.path.join(root, file)
                member_name = file.replace("_support_files.tar.gz", "")
                member_output = os.path.join(members_dir, member_name)
                try:
                    parse_vsf_member(member_tar, member_output)
                except Exception as e:
                    print(f"⚠️ Failed to parse VSF member {file}: {e}")
    
    
     # Handle previous boot logs in main bundle
    parse_previous_boot_logs(bundle_dir, output_dir)
    
    readme_path = find_readme()
    if readme_path:
        try:
            shutil.copy(readme_path, Path(output_dir) / "README.md")
            print(f"📄 Copied README.md from {readme_path} to {output_dir}")
        except Exception as e:
            print(f"❌ Failed to copy README.md: {e}")
    else:
        print("⚠️ README.md not found using find_readme()")

    try:
        shutil.rmtree(bundle_dir)
        print(f" Cleaned up temporary directory: {bundle_dir}")
    except Exception as e:
        print(f" Failed to clean temporary directory {bundle_dir}: {e}")

    return output_dir







