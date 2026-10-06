"""Host Compose helper: one explicit project, independent of the caller's directory."""
from pathlib import Path
import subprocess
import sys

PROJECT_NAME = "open-table-formats-lab"
LOCAL_LAB = Path(__file__).resolve().parents[1]

def compose_command(*arguments, olist=True):
    command = ["docker", "compose", "-p", PROJECT_NAME, "--project-directory", str(LOCAL_LAB),
               "-f", str(LOCAL_LAB / "docker-compose.yml")]
    if olist:
        command.extend(["-f", str(LOCAL_LAB / "docker-compose.olist.yml")])
    return command + list(arguments)

if __name__ == "__main__":
    sys.exit(subprocess.call(compose_command(*sys.argv[1:]), cwd=LOCAL_LAB))
