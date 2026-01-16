#!/bin/bash

echo "Installing required packages..."
pip install -r requirements.txt

echo "Starting the cluster simulation server with Supabase integration..."
python server_new.py &
SERVER_PID=$!

echo "Wait for the server to initialize..."
sleep 5

echo "Adding a test node with 8 CPU cores and 16GB memory..."
python client.py add_node --cpu 8 --memory 16

echo "Launching a test pod with 2 CPU cores..."
python client.py launch_pod --cpu_required 2 --memory_required 4

echo "Listing all nodes in the cluster..."
python client.py list_nodes

echo "Dashboard is available at http://localhost:5000"
echo ""
echo "You can now explore the dashboard in your web browser!"
echo "Opening the dashboard..."
python client.py dashboard
echo ""
echo "Press Ctrl+C to stop the server when finished."

# Wait for Ctrl+C
wait $SERVER_PID 