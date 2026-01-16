import argparse
import requests
import sys
import webbrowser

def add_node(server_url, cpu, memory, node_type, network_group):
    url = f"{server_url}/api/add_node"
    payload = {
        "cpu": cpu, 
        "memory": memory,
        "node_type": node_type,
        "network_group": network_group
    }
    response = requests.post(url, json=payload)
    if response.status_code == 200:
        data = response.json()
        print(f"Node added. Node ID: {data['node_id']}")
        return data["node_id"]
    else:
        print("Error adding node:", response.json())
        sys.exit(1)

def launch_pod(server_url, cpu_required, memory_required, scheduling_algorithm, network_group, node_affinity):
    url = f"{server_url}/api/launch_pod"
    payload = {
        "cpu_required": cpu_required,
        "memory_required": memory_required,
        "scheduling_algorithm": scheduling_algorithm,
        "network_group": network_group
    }
    
    if node_affinity:
        payload["node_affinity"] = node_affinity
       
    response = requests.post(url, json=payload)
    if response.status_code == 200:
        data = response.json()
        print(f"Pod {data['pod_id']} scheduled on node {data['assigned_node']} using {data['scheduling_algorithm']}")
    else:
        print("Error launching pod:", response.json())

def list_nodes(server_url):
    url = f"{server_url}/api/list_nodes"
    response = requests.get(url)
    if response.status_code == 200:
        data = response.json()
        for node in data["nodes"]:
            print(f"Node ID: {node['node_id']}")
            print(f"   CPU Total: {node['cpu_total']}, CPU Available: {node['cpu_available']}")
            print(f"   Memory Total: {node['memory_total']}GB, Memory Available: {node['memory_available']}GB")
            print(f"   Status: {node['status']}")
            print("   Pods:")
            for pod in node["pods"]:
                print(f"      {pod['pod_id']} | CPU Req: {pod['cpu']} | Mem Req: {pod['memory']} | Group: {pod.get('network_group','default')}")
            print("")
    else:
        print("Error listing nodes:", response.json())

def chaos_monkey(server_url):
    url = f"{server_url}/api/chaos_monkey"
    response = requests.post(url)
    if response.status_code == 200:
        data = response.json()
        print(data["message"])
    else:
        print("Error triggering Chaos Monkey:", response.json())

def open_dashboard(server_url):
    url = server_url
    print(f"Opening dashboard at {url}")
    webbrowser.open(url)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="CLI client for Cluster Simulation Framework")
    parser.add_argument("--server", default="http://localhost:5000", help="API server base URL")
    subparsers = parser.add_subparsers(dest="command", required=True)

    parser_add = subparsers.add_parser("add_node", help="Add a node to the cluster")
    parser_add.add_argument("--cpu", type=int, required=True, help="Number of CPU cores")
    parser_add.add_argument("--memory", type=int, default=16, help="Memory in GB (default: 16)")
    parser_add.add_argument("--node_type", type=str, choices=["balanced", "high_cpu", "high_mem"], default="balanced", help="Node type")
    parser_add.add_argument("--network_group", type=str, default="default", help="Network group")

    parser_pod = subparsers.add_parser("launch_pod", help="Launch a pod with given requirements")
    parser_pod.add_argument("--cpu_required", type=int, required=True, help="CPU cores required")
    parser_pod.add_argument("--memory_required", type=int, default=4, help="Memory in GB required (default: 4)")
    parser_pod.add_argument("--scheduling_algorithm", type=str, choices=["first_fit", "best_fit", "worst_fit"], default="first_fit", help="Scheduling algorithm")
    parser_pod.add_argument("--network_group", type=str, default="default", help="Network group")
    parser_pod.add_argument("--node_affinity", type=str, choices=["", "balanced", "high_cpu", "high_mem"], default="", help="Node affinity")

    subparsers.add_parser("list_nodes", help="List all nodes in the cluster")
    subparsers.add_parser("chaos_monkey", help="Trigger a Chaos Monkey event")
    subparsers.add_parser("dashboard", help="Open the web dashboard in a browser")

    args = parser.parse_args()
    if args.command == "add_node":
        add_node(args.server, args.cpu, args.memory, args.node_type, args.network_group)
    elif args.command == "launch_pod":
        launch_pod(args.server, args.cpu_required, args.memory_required, args.scheduling_algorithm, args.network_group, args.node_affinity)
    elif args.command == "list_nodes":
        list_nodes(args.server)
    elif args.command == "chaos_monkey":
        chaos_monkey(args.server)
    elif args.command == "dashboard":
        open_dashboard(args.server)
    else:
        parser.print_help()
