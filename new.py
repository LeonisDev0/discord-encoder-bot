import subprocess

result = subprocess.run(["aria2c", "--version"], capture_output=True, text=True)
print(result.stdout)
print(result.stderr)
