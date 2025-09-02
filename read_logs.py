#!/usr/bin/env python3
"""
Convenience wrapper for the log reading utility.
Automatically looks for yulia logs in logs/yulia_agent_prompt_logs/
"""
import sys
import subprocess
from pathlib import Path
import glob

def main():
    # Get the directory of this script
    script_dir = Path(__file__).parent
    log_utils_script = script_dir / "log_utils" / "read_complete_logs.py"
    
    if not log_utils_script.exists():
        print("Error: Log utilities not found in log_utils directory")
        sys.exit(1)
    
    if len(sys.argv) == 1:
        # No arguments provided, show available logs
        yulia_logs_dir = script_dir / "logs" / "yulia_agent_prompt_logs"
        if yulia_logs_dir.exists():
            log_files = list(yulia_logs_dir.glob("yulia_logs_*.jsonl"))
            if log_files:
                print("Available yulia log files:")
                for log_file in sorted(log_files):
                    print(f"  {log_file.name}")
                print(f"\nUsage: python read_logs.py <log_filename> [options]")
                print(f"Example: python read_logs.py {log_files[-1].name} --no-truncate")
            else:
                print("No yulia log files found in logs/yulia_agent_prompt_logs/")
        else:
            print("No logs directory found")
        return
    
    # Check if the first argument is just a filename (not a full path)
    log_arg = sys.argv[1]
    if not log_arg.startswith('/') and not log_arg.startswith('./') and not log_arg.startswith('../'):
        # Assume it's a filename in the yulia logs directory
        yulia_logs_dir = script_dir / "logs" / "yulia_agent_prompt_logs"
        full_path = yulia_logs_dir / log_arg
        if full_path.exists():
            sys.argv[1] = str(full_path)
    
    # Pass all arguments to the actual script
    cmd = [sys.executable, str(log_utils_script)] + sys.argv[1:]
    subprocess.run(cmd)

if __name__ == "__main__":
    main()
