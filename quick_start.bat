@echo off
echo Installing required packages...
pip install -r requirements.txt

echo Checking MySQL connection...
python test_mysql.py
if %ERRORLEVEL% NEQ 0 (
    echo MySQL connection failed. Please check your .env file and MySQL server.
    pause
    exit /b
)

echo Starting the cluster simulation server with MySQL integration...
start python server_new.py

echo Wait for the server to initialize...
timeout /t 5

echo Adding a test node with 8 CPU cores and 16GB memory...
python client.py add_node --cpu 8 --memory 16

echo Launching a test pod with 2 CPU cores...
python client.py launch_pod --cpu_required 2 --memory_required 4

echo Listing all nodes in the cluster...
python client.py list_nodes

echo Dashboard is available at http://localhost:5000
echo.
echo You can now explore the dashboard in your web browser!
echo Opening the dashboard...
python client.py dashboard
echo.
echo Press any key to exit...
pause > nul 