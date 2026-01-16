# Cluster Simulation Framework - Project Overview

## Project Summary
This project simulates a container orchestration system (similar to Kubernetes) that manages nodes and pods in a cluster. It provides a real-time dashboard for monitoring and management, complete with visualizations and analytics.

## Key Components

### 1. Server (server_2.py)
The main server component that:
- Manages nodes and pods in the cluster
- Provides REST API endpoints for cluster operations
- Serves the real-time dashboard
- Handles pod scheduling with different algorithms
- Performs health monitoring and auto-scaling
- Simulates node failures via Chaos Monkey

### 2. Client (client.py)
A command-line interface to interact with the server:
- Adding nodes with specified CPU and memory
- Launching pods with resource requirements
- Listing all nodes in the cluster
- Triggering Chaos Monkey for failure testing

### 3. Node Simulator (node.py)
Simulates node behavior by sending regular heartbeats to the server

### 4. Docker Integration
Optionally runs node simulators in containers for more realistic simulation

## Features Explained

### Node Management
- Adding nodes with specific CPU and memory resources
- Heartbeat-based health monitoring
- Auto-scaling capability when cluster utilization exceeds threshold
- Failure detection and recovery

### Pod Scheduling
The system implements three scheduling algorithms:
- **First Fit**: Places pods on the first node with sufficient resources
- **Best Fit**: Places pods on the node with the least remaining resources
- **Worst Fit**: Places pods on the node with the most available resources

### Network Groups and Affinity
- Pods can be assigned to network groups for isolation
- Node affinity allows targeting specific node types

### Dashboard Visualization
- Real-time monitoring of cluster state
- Interactive visualizations of resource usage
- 3D node graph for visualizing cluster topology
- Event logging and history tracking

## How it Works

1. The server initializes and sets up an SQLite database for persistent state
2. Background monitoring threads check node health, simulate heartbeats, and manage auto-scaling
3. The client communicates with the server via REST APIs
4. Node simulators send heartbeats to maintain their active status
5. The dashboard updates in real-time using Socket.IO for WebSocket communication

## Project Strengths
- **Educational Value**: Demonstrates microservices architecture and orchestration concepts
- **Visualization**: Advanced real-time dashboard with modern visualization libraries
- **Scalability**: Support for multiple scheduling algorithms and node types
- **Persistence**: Data storage in SQLite for durability
- **Interactivity**: Real-time updates and interactive dashboard elements

## Running the Project
1. Install dependencies: `pip install -r requirements.txt`
2. Run the server: `python server_2.py`
3. Access dashboard: http://localhost:5000/dashboard
4. Use client to interact: `python client.py add_node --cpu 8 --memory 16`

## Future Enhancements
- Adding more sophisticated scheduling algorithms
- Implementing pod resource limits and QoS classes
- Supporting pod dependencies and service discovery
- Adding pod network policies and security features 