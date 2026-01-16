import os
import time
import mysql.connector
from mysql.connector import Error
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# MySQL connection configuration
DB_CONFIG = {
    'host': os.environ.get('MYSQL_HOST', 'localhost'),
    'user': os.environ.get('MYSQL_USER', 'root'),
    'password': os.environ.get('MYSQL_PASSWORD', ''),
    'database': os.environ.get('MYSQL_DATABASE', 'cluster_sim')
}

# Global connection object
db_connection = None
db_cursor = None

def connect_to_mysql():
    """Connect to MySQL database."""
    global db_connection, db_cursor
    try:
        db_connection = mysql.connector.connect(**DB_CONFIG)
        db_cursor = db_connection.cursor(dictionary=True)
        print("✅ Successfully connected to MySQL database")
        return True
    except Error as e:
        print(f"❌ Failed to connect to MySQL database: {e}")
        return False

def execute_query(query, params=None, fetch=True):
    """Execute a query and optionally fetch results."""
    global db_connection, db_cursor
    
    # Reconnect if connection is closed
    if db_connection is None or not db_connection.is_connected():
        if not connect_to_mysql():
            return None if fetch else False
    
    try:
        db_cursor.execute(query, params or ())
        if fetch:
            result = db_cursor.fetchall()
            return result
        else:
            db_connection.commit()
            return True
    except Error as e:
        print(f"Error executing query: {e}")
        print(f"Query: {query}")
        print(f"Params: {params}")
        if not fetch:
            db_connection.rollback()
        return None if fetch else False

def init_mysql_tables():
    """Create MySQL tables if they don't exist."""
    # Create nodes table
    nodes_table_query = """
    CREATE TABLE IF NOT EXISTS nodes (
        node_id VARCHAR(50) PRIMARY KEY,
        cpu_total INT NOT NULL,
        cpu_available INT NOT NULL,
        memory_total INT NOT NULL,
        memory_available INT NOT NULL,
        node_type VARCHAR(20) NOT NULL,
        network_group VARCHAR(50) NOT NULL,
        last_heartbeat FLOAT,
        status VARCHAR(20) NOT NULL,
        simulate_heartbeat BOOLEAN NOT NULL,
        container_id VARCHAR(100)
    )
    """
    
    # Create pods table
    pods_table_query = """
    CREATE TABLE IF NOT EXISTS pods (
        pod_id VARCHAR(50) PRIMARY KEY,
        node_id VARCHAR(50) NOT NULL,
        cpu INT NOT NULL,
        memory INT NOT NULL,
        network_group VARCHAR(50) NOT NULL,
        node_affinity VARCHAR(20)
    )
    """
    
    # Create event_logs table
    event_logs_table_query = """
    CREATE TABLE IF NOT EXISTS event_logs (
        id INT AUTO_INCREMENT PRIMARY KEY,
        timestamp FLOAT NOT NULL,
        event TEXT NOT NULL
    )
    """
    
    # Create utilization_history table
    utilization_table_query = """
    CREATE TABLE IF NOT EXISTS utilization_history (
        id INT AUTO_INCREMENT PRIMARY KEY,
        timestamp FLOAT NOT NULL,
        utilization FLOAT NOT NULL
    )
    """
    
    # Execute queries
    if not execute_query(nodes_table_query, fetch=False):
        return False
    if not execute_query(pods_table_query, fetch=False):
        return False
    if not execute_query(event_logs_table_query, fetch=False):
        return False
    if not execute_query(utilization_table_query, fetch=False):
        return False
    
    return True

def get_nodes():
    """Retrieve all nodes from MySQL."""
    query = "SELECT * FROM nodes"
    return execute_query(query) or []

def get_pods():
    """Retrieve all pods from MySQL."""
    query = "SELECT * FROM pods"
    return execute_query(query) or []

def get_logs():
    """Retrieve event logs from MySQL."""
    query = "SELECT * FROM event_logs ORDER BY timestamp DESC LIMIT 50"
    return execute_query(query) or []

def get_utilization_history():
    """Retrieve utilization history from MySQL."""
    query = "SELECT * FROM utilization_history ORDER BY timestamp DESC LIMIT 50"
    return execute_query(query) or []

def save_node(node):
    """Save or update a node in MySQL."""
    try:
        # Check if node exists
        check_query = "SELECT 1 FROM nodes WHERE node_id = %s"
        result = execute_query(check_query, (node['node_id'],))
        
        if result:
            # Update existing node
            update_query = """
            UPDATE nodes 
            SET cpu_total = %s, cpu_available = %s, memory_total = %s, memory_available = %s,
                node_type = %s, network_group = %s, last_heartbeat = %s, status = %s,
                simulate_heartbeat = %s, container_id = %s
            WHERE node_id = %s
            """
            params = (
                node['cpu_total'], node['cpu_available'], node['memory_total'], node['memory_available'],
                node['node_type'], node['network_group'], node.get('last_heartbeat'), node['status'],
                node['simulate_heartbeat'], node.get('container_id'), node['node_id']
            )
            success = execute_query(update_query, params, fetch=False)
        else:
            # Insert new node
            insert_query = """
            INSERT INTO nodes (node_id, cpu_total, cpu_available, memory_total, memory_available,
                            node_type, network_group, last_heartbeat, status, simulate_heartbeat, container_id)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """
            params = (
                node['node_id'], node['cpu_total'], node['cpu_available'], node['memory_total'], node['memory_available'],
                node['node_type'], node['network_group'], node.get('last_heartbeat'), node['status'],
                node['simulate_heartbeat'], node.get('container_id')
            )
            success = execute_query(insert_query, params, fetch=False)
        
        print(f"[DEBUG-DB] {'Updated' if result else 'Inserted'} node {node['node_id']} with status={node['status']}")
        return success
    except Exception as e:
        print(f"Error saving node: {e}")
        return False

def delete_node(node_id):
    """Delete a node and its associated pods from MySQL."""
    try:
        # Delete pods associated with this node
        delete_pods_query = "DELETE FROM pods WHERE node_id = %s"
        execute_query(delete_pods_query, (node_id,), fetch=False)
        
        # Delete the node
        delete_node_query = "DELETE FROM nodes WHERE node_id = %s"
        success = execute_query(delete_node_query, (node_id,), fetch=False)
        
        return success
    except Exception as e:
        print(f"Error deleting node: {e}")
        return False

def save_pod(pod):
    """Save or update a pod in MySQL."""
    try:
        # Check if pod exists
        check_query = "SELECT 1 FROM pods WHERE pod_id = %s"
        result = execute_query(check_query, (pod['pod_id'],))
        
        if result:
            # Update existing pod
            if 'node_affinity' in pod:
                update_query = """
                UPDATE pods 
                SET node_id = %s, cpu = %s, memory = %s, network_group = %s, node_affinity = %s
                WHERE pod_id = %s
                """
                params = (
                    pod['node_id'], pod['cpu'], pod['memory'], pod['network_group'], 
                    pod['node_affinity'], pod['pod_id']
                )
            else:
                update_query = """
                UPDATE pods 
                SET node_id = %s, cpu = %s, memory = %s, network_group = %s
                WHERE pod_id = %s
                """
                params = (
                    pod['node_id'], pod['cpu'], pod['memory'], pod['network_group'], pod['pod_id']
                )
            success = execute_query(update_query, params, fetch=False)
        else:
            # Insert new pod
            if 'node_affinity' in pod:
                insert_query = """
                INSERT INTO pods (pod_id, node_id, cpu, memory, network_group, node_affinity)
                VALUES (%s, %s, %s, %s, %s, %s)
                """
                params = (
                    pod['pod_id'], pod['node_id'], pod['cpu'], pod['memory'], 
                    pod['network_group'], pod['node_affinity']
                )
            else:
                insert_query = """
                INSERT INTO pods (pod_id, node_id, cpu, memory, network_group)
                VALUES (%s, %s, %s, %s, %s)
                """
                params = (
                    pod['pod_id'], pod['node_id'], pod['cpu'], pod['memory'], pod['network_group']
                )
            success = execute_query(insert_query, params, fetch=False)
        
        return success
    except Exception as e:
        print(f"Error saving pod: {e}")
        return False

def update_pod_node(pod_id, new_node_id):
    """Update the node assignment for a pod."""
    try:
        query = "UPDATE pods SET node_id = %s WHERE pod_id = %s"
        success = execute_query(query, (new_node_id, pod_id), fetch=False)
        return success
    except Exception as e:
        print(f"Error updating pod node: {e}")
        return False

def log_event(event):
    """Log an event to MySQL."""
    try:
        query = "INSERT INTO event_logs (timestamp, event) VALUES (%s, %s)"
        success = execute_query(query, (time.time(), event), fetch=False)
        return success
    except Exception as e:
        print(f"Error logging event: {e}")
        return False

def record_utilization(utilization):
    """Record cluster utilization to MySQL."""
    try:
        query = "INSERT INTO utilization_history (timestamp, utilization) VALUES (%s, %s)"
        success = execute_query(query, (time.time(), utilization), fetch=False)
        return success
    except Exception as e:
        print(f"Error recording utilization: {e}")
        return False

def close_connection():
    """Close the MySQL connection."""
    global db_connection, db_cursor
    if db_cursor:
        db_cursor.close()
    if db_connection and db_connection.is_connected():
        db_connection.close()
        print("MySQL connection closed")