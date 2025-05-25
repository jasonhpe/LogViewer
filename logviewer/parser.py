import platform
import os
import re
import tarfile
import uuid
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
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed

LOG_FILE_PREFIXES = ["event", "messages", "supportlog", "critical", "diagdump"]

def safe_parse(path):
    try:
        output_dir = f"{Path(path).stem}_log_analysis_results"
        if not os.path.exists(os.path.join(output_dir, "parsed_logs.json")):
            parse_bundle(path, output_dir)
        return {"path": path, "status": "Success", "output": output_dir}
    except Exception as e:
        return {"path": path, "status": "Error", "error": str(e)}

def parse_multiple_bundles(bundle_paths, workers=4):
    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = [executor.submit(safe_parse, path) for path in bundle_paths]
        results = []
        for future in as_completed(futures):
            results.append(future.result())
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
    def handle_boot_folder(entry):
        boot_path = os.path.join(member_extracted_dir, entry)
        if not os.path.isdir(boot_path) or not entry.startswith("boot"):
            return
        print(f"🧠 Parsing VSF flat boot folder: {entry}")
        out_path = os.path.join(member_output_dir, "previous", entry)
        os.makedirs(out_path, exist_ok=True)

        logs = []
        fastlog_entries = []
        fastlog_files = []

        def get_logs():
            nonlocal logs
            logs = collect_event_logs(boot_path)

        def get_fastlog_entries():
            nonlocal fastlog_entries
            fastlog_entries = collect_fastlog_entries(boot_path)

        def get_fastlog_files():
            nonlocal fastlog_files
            fastlog_files = collect_fastlogs(boot_path, out_path)

        threads = []
        for fn in [get_logs, get_fastlog_entries, get_fastlog_files]:
            t = threading.Thread(target=fn)
            t.start()
            threads.append(t)
        for t in threads:
            t.join()

        logs.extend(fastlog_entries)
        logs.sort(key=lambda x: datetime.fromisoformat(x["timestamp"]))

        if not logs:
            print(f"⚠️ No logs parsed from {boot_path}")

        with open(os.path.join(out_path, "parsed_logs.json"), "w") as f:
            json.dump(logs, f, indent=2)
        with open(os.path.join(out_path, "fastlog_index.json"), "w") as f:
            json.dump(fastlog_files, f, indent=2)

    threads = []
    for entry in os.listdir(member_extracted_dir):
        t = threading.Thread(target=handle_boot_folder, args=(entry,))
        t.start()
        threads.append(t)
    for t in threads:
        t.join()

def parse_previous_boot_logs(bundle_dir, output_dir):
    prev_dir = os.path.join(bundle_dir, "prev_boot_logs")  # Updated directory name
    if not os.path.exists(prev_dir):
        return

    def handle_boot_folder(entry):
        boot_path = os.path.join(prev_dir, entry)
        if not os.path.isdir(boot_path) or not entry.startswith("boot"):
            return
        print(f"🔁 Parsing previous boot: {entry}")
        out_path = os.path.join(output_dir, "previous", entry)
        os.makedirs(out_path, exist_ok=True)

        logs = []
        fastlog_entries = []

        def get_logs():
            nonlocal logs
            logs = collect_event_logs(boot_path)

        def get_fastlogs():
            nonlocal fastlog_entries
            fastlog_entries = collect_fastlog_entries(boot_path)

        t1 = threading.Thread(target=get_logs)
        t2 = threading.Thread(target=get_fastlogs)
        t1.start()
        t2.start()
        t1.join()
        t2.join()

        logs.extend(fastlog_entries)
        logs.sort(key=lambda x: datetime.fromisoformat(x["timestamp"]))

        if not logs:
            print(f"⚠️ No logs parsed from {boot_path}")

        with open(os.path.join(out_path, "parsed_logs.json"), "w") as f:
            json.dump(logs, f, indent=2)

        collect_fastlogs(boot_path, out_path)

    threads = []
    for entry in os.listdir(prev_dir):
        t = threading.Thread(target=handle_boot_folder, args=(entry,))
        t.start()
        threads.append(t)
    for t in threads:
        t.join()
	    
def parse_vsf_member(tar_path, member_output_dir):
    print(f"📦 Parsing VSF member bundle: {tar_path}")
    extracted = extract_bundle(tar_path, target_dir=member_output_dir + "_tmp")
    if not extracted:
        print(f"⚠️ Could not extract {tar_path}")
        return

    logs = []
    fastlog_entries = []
    fastlog_files = []

    def get_logs():
        nonlocal logs
        logs = collect_event_logs(extracted)

    def get_fastlog_entries():
        nonlocal fastlog_entries
        fastlog_entries = collect_fastlog_entries(extracted)

    def get_fastlog_files():
        nonlocal fastlog_files
        fastlog_files = collect_fastlogs(extracted, member_output_dir)

    threads = []
    for fn in [get_logs, get_fastlog_entries, get_fastlog_files]:
        t = threading.Thread(target=fn)
        t.start()
        threads.append(t)
    for t in threads:
        t.join()

    logs.extend(fastlog_entries)
    logs.sort(key=lambda x: datetime.fromisoformat(x["timestamp"]))

    os.makedirs(member_output_dir, exist_ok=True)
    with open(os.path.join(member_output_dir, "parsed_logs.json"), "w") as f:
        json.dump(logs, f, indent=2)
    with open(os.path.join(member_output_dir, "fastlog_index.json"), "w") as f:
        json.dump(fastlog_files, f, indent=2)

    # Copy diagdump_*.txt to feature folder
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

            if file.endswith(".gz") and any(file.startswith(prefix) for prefix in LOG_FILE_PREFIXES):
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

            if file.endswith(".log") or "journal" in file:
                for line in read_lines(full_path):
                    entry = parse_line(line)
                    if entry:
                        entry["source"] = "eventlog"
                        logs.append(entry)

    return logs

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

    def process_file(fname, root):
        full_path = os.path.join(root, fname)
        temp_decompressed = None

        if fname.endswith(".gz"):
            try:
                temp_decompressed = os.path.join(tempfile.gettempdir(), f"{uuid.uuid4()}_{fname.replace('.gz', '')}")
                with gzip.open(full_path, "rb") as f_in, open(temp_decompressed, "wb") as f_out:
                    shutil.copyfileobj(f_in, f_out)
                full_path = temp_decompressed
            except Exception as e:
                print(f"⚠️ Failed to decompress {fname}: {e}")
                return None

        cmd = [fastlog_cmd, "-v", full_path] if isinstance(fastlog_cmd, str) else fastlog_cmd + ["-v", translate_path_for_wsl(full_path)]

        try:
            result = subprocess.run(cmd, stdout=subprocess.PIPE, text=True)
            out_file = os.path.join(fastlog_output_dir, os.path.basename(full_path) + ".txt")
            with open(out_file, "w") as f:
                f.write(result.stdout)
            return os.path.basename(out_file)
        except Exception as e:
            print(f"⚠️ Failed to parse {fname}: {e}")
            return None
        finally:
            if temp_decompressed and os.path.exists(temp_decompressed):
                try:
                    os.remove(temp_decompressed)
                except Exception as e:
                    print(f"⚠️ Could not delete temp file {temp_decompressed}: {e}")

    with ThreadPoolExecutor() as executor:
        futures = [executor.submit(process_file, fname, root)
                   for root, _, files in os.walk(bundle_dir)
                   for fname in files if fname.endswith(".supportlog") or fname.endswith(".supportlog.gz")]
        for future in as_completed(futures):
            result = future.result()
            if result:
                fastlog_files.append(result)

    return fastlog_files
	
def collect_fastlog_entries(bundle_dir):
    fastlog_cmd = get_fastlog_parser()
    entries = []

    def process_file(fname, root):
        full_path = os.path.join(root, fname)
        process_name = os.path.basename(fname).replace(".supportlog", "").replace(".gz", "")
        temp_decompressed = None

        if fname.endswith(".gz"):
            try:
                temp_decompressed = os.path.join(tempfile.gettempdir(), f"{uuid.uuid4()}_{fname.replace('.gz', '')}")
                with gzip.open(full_path, "rb") as f_in, open(temp_decompressed, "wb") as f_out:
                    shutil.copyfileobj(f_in, f_out)
                full_path = temp_decompressed
            except Exception as e:
                print(f"⚠️ Failed to decompress {fname}: {e}")
                return []

        cmd = [fastlog_cmd, "-v", full_path] if isinstance(fastlog_cmd, str) else fastlog_cmd + ["-v", translate_path_for_wsl(full_path)]

        local_entries = []
        try:
            result = subprocess.run(cmd, stdout=subprocess.PIPE, text=True)
            lines = result.stdout.splitlines()
            buffer = []
            timestamp = None
            for line in lines:
                if re.match(r"\(\d{2} \w{3} \d{2} \d{2}:\d{2}:\d{2}\.\d+", line):
                    if buffer and timestamp:
                        local_entries.append({
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
                local_entries.append({
                    "timestamp": timestamp,
                    "process": process_name,
                    "message": "\n".join(buffer),
                    "source": "fastlog"
                })
        except Exception as e:
            print(f"⚠️ Failed to extract fastlog entries from {fname}: {e}")
        finally:
            if temp_decompressed and os.path.exists(temp_decompressed):
                try:
                    os.remove(temp_decompressed)
                except Exception as e:
                    print(f"⚠️ Could not delete temp file {temp_decompressed}: {e}")

        return local_entries

    with ThreadPoolExecutor() as executor:
        futures = [executor.submit(process_file, fname, root)
                   for root, _, files in os.walk(bundle_dir)
                   for fname in files if fname.endswith(".supportlog") or fname.endswith(".supportlog.gz")]
        for future in as_completed(futures):
            entries.extend(future.result())

    return entries

def collect_showtech_and_diag(bundle_dir):
    showtech = None
    diag = {}
    isp = None

    def handle_file(file, root):
        nonlocal showtech, diag, isp
        try:
            if file == "showtech.txt":
                showtech = os.path.join(root, file)
            elif file == "isp.txt":
                isp = os.path.join(root, file)
            elif file == "diagdump.txt" and "feature" in root:
                rel_dir = os.path.relpath(root, bundle_dir)
                diag[rel_dir] = os.path.join(root, file)
        except Exception as e:
            print(f"⚠️ Error processing file in showtech/diag pass: {e}")

    threads = []
    for root, _, files in os.walk(bundle_dir):
        for file in files:
            t = threading.Thread(target=handle_file, args=(file, root))
            threads.append(t)
            t.start()

    for t in threads:
        t.join()

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

    logs = []
    fastlog_entries = []
    fastlog_files = []

    # Run log collection phases in parallel
    def collect_logs():
        nonlocal logs
        logs = collect_event_logs(bundle_dir)

    def collect_fastlog():
        nonlocal fastlog_entries
        fastlog_entries = collect_fastlog_entries(bundle_dir)

    def collect_fastlog_files():
        nonlocal fastlog_files
        fastlog_files = collect_fastlogs(bundle_dir, output_dir)

    threads = []
    for fn in [collect_logs, collect_fastlog, collect_fastlog_files]:
        t = threading.Thread(target=fn)
        t.start()
        threads.append(t)
    for t in threads:
        t.join()

    logs.extend(fastlog_entries)
    logs.sort(key=lambda x: datetime.fromisoformat(x["timestamp"]))

    with open(os.path.join(output_dir, "parsed_logs.json"), "w") as f:
        json.dump(logs, f, indent=2)
    with open(os.path.join(output_dir, "fastlog_index.json"), "w") as f:
        json.dump(fastlog_files, f, indent=2)

    # Collect showtech and diag
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

    # Parse VSF members in parallel
    members_dir = os.path.join(output_dir, "members")
    os.makedirs(members_dir, exist_ok=True)

    vsf_threads = []
    for root, _, files in os.walk(bundle_dir):
        for file in files:
            if re.match(r"mem_\d+_support_files\.tar\.gz", file):
                member_tar = os.path.join(root, file)
                member_name = file.replace("_support_files.tar.gz", "")
                member_output = os.path.join(members_dir, member_name)
                t = threading.Thread(target=parse_vsf_member, args=(member_tar, member_output))
                vsf_threads.append(t)
                t.start()
    for t in vsf_threads:
        t.join()

    # Parse previous boots
    parse_previous_boot_logs(bundle_dir, output_dir)

    # Add README if found
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
        print(f"🧹 Cleaned up temporary directory: {bundle_dir}")
    except Exception as e:
        print(f"⚠️ Failed to clean temporary directory {bundle_dir}: {e}")

    return output_dir






