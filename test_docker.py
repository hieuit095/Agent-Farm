import docker
client = docker.from_env()
print("Docker version:", client.version()["Version"])
