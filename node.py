import time
import requests
import argparse

def send_heartbeat(server_url, node_id, heartbeat_interval):
    url = f"{server_url}/api/heartbeat"
    while True:
        try:
            response = requests.post(url, json={"node_id": node_id})
            if response.status_code == 200:
                print(f"[{time.ctime()}] Heartbeat sent for node {node_id}")
            else:
                print(f"[{time.ctime()}] Heartbeat error: {response.json()}")
        except Exception as e:
            print(f"[{time.ctime()}] Exception during heartbeat: {e}")
        time.sleep(heartbeat_interval)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Node simulator for Cluster Simulation Framework")
    parser.add_argument("--server", default="http://localhost:5000", help="API server base URL")
    parser.add_argument("--node_id", required=True, help="Unique node_id assigned by the API server")
    parser.add_argument("--interval", type=int, default=7, help="Heartbeat interval (seconds)")
    args = parser.parse_args()
    send_heartbeat(args.server, args.node_id, args.interval)
