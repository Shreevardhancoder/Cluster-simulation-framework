import os
import time
from dotenv import load_dotenv
from mysql_db import (
    connect_to_mysql, init_mysql_tables, get_nodes, save_node,
    get_pods, save_pod, log_event, close_connection
)

# Load environment variables
load_dotenv()

def test_mysql_operations():
    """Test basic MySQL database operations."""
    print("Testing MySQL database operations...")
    
    # Connect to MySQL
    if not connect_to_mysql():
        print("Failed to connect to MySQL database.")
        return False
    
    # Initialize tables
    if not init_mysql_tables():
        print("Failed to initialize MySQL tables.")
        return False
    
    print("Successfully initialized MySQL tables.")
    
    # Test node operations
    test_node = {
        "node_id": f"test_node_{int(time.time())}",
        "cpu_total": 8,
        "cpu_available": 8,
        "memory_total": 16,
        "memory_available": 16,
        "node_type": "balanced",
        "network_group": "default",
        "last_heartbeat": time.time(),
        "status": "active",
        "simulate_heartbeat": True
    }
    
    print(f"Adding test node {test_node['node_id']}...")
    if not save_node(test_node):
        print("Failed to save test node.")
        return False
    
    # Verify node was saved
    nodes = get_nodes()
    node_found = False
    for node in nodes:
        if node["node_id"] == test_node["node_id"]:
            node_found = True
            break
    
    if not node_found:
        print("Test node not found in database.")
        return False
    
    print("Successfully saved and retrieved test node.")
    
    # Test pod operations
    test_pod = {
        "pod_id": f"test_pod_{int(time.time())}",
        "node_id": test_node["node_id"],
        "cpu": 2,
        "memory": 4,
        "network_group": "default"
    }
    
    print(f"Adding test pod {test_pod['pod_id']}...")
    if not save_pod(test_pod):
        print("Failed to save test pod.")
        return False
    
    # Verify pod was saved
    pods = get_pods()
    pod_found = False
    for pod in pods:
        if pod["pod_id"] == test_pod["pod_id"]:
            pod_found = True
            break
    
    if not pod_found:
        print("Test pod not found in database.")
        return False
    
    print("Successfully saved and retrieved test pod.")
    
    # Test event logging
    print("Testing event logging...")
    if not log_event("Test event from MySQL test script"):
        print("Failed to log event.")
        return False
    
    print("Successfully logged event.")
    
    # Close connection
    close_connection()
    
    print("All MySQL database operations tested successfully!")
    return True

if __name__ == "__main__":
    # Create a .env file with MySQL connection details if it doesn't exist
    if not os.path.exists(".env"):
        print("Creating .env file with default MySQL connection details...")
        with open(".env", "w") as f:
            f.write("MYSQL_HOST=localhost\n")
            f.write("MYSQL_USER=root\n")
            f.write("MYSQL_PASSWORD=\n")
            f.write("MYSQL_DATABASE=cluster_sim\n")
        print("Created .env file. Please update it with your MySQL connection details.")
    
    # Run tests
    test_mysql_operations()