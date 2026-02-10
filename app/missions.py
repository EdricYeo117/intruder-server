# app/missions.py
from app.drone_sse import enqueue_command

DRONE_DEVICE_ID = "android-controller-01"

async def dispatch_intrusion_mission(server_ip: str):
    await enqueue_command(DRONE_DEVICE_ID, "VS_ENABLE", {"enabled": True})

    moves = [
        {"leftX": 0, "leftY": 0, "rightX": 0, "rightY": 0.25, "durationMs": 800, "hz": 25},
        {"leftX": 0, "leftY": 0, "rightX": 0, "rightY": -0.25, "durationMs": 800, "hz": 25},
        {"leftX": 0, "leftY": 0, "rightX": 0.25, "rightY": 0, "durationMs": 800, "hz": 25},
        {"leftX": 0, "leftY": 0, "rightX": -0.25, "rightY": 0, "durationMs": 800, "hz": 25},
    ]
    await enqueue_command(DRONE_DEVICE_ID, "MOVE_SEQUENCE", {"moves": moves, "defaultHz": 25})
    await enqueue_command(DRONE_DEVICE_ID, "SNAPSHOT", {"upload_url": f"http://{server_ip}:8080/v1/drone/uploads/photo"})
