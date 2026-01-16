import time
import uuid
import random
import csv
import io
import sqlite3
from flask import Flask, request, jsonify, render_template_string, send_file
from flask_socketio import SocketIO, emit
from threading import Thread, RLock

# ---- Docker SDK & Network‐Policy Setup ----
import docker
from docker.errors import NotFound, DockerException

DOCKER_NODE_IMAGE       = "node-simulator:latest"
NODE_HEARTBEAT_INTERVAL = 7  # seconds
try:
    docker_client = docker.from_env()
except DockerException:
    docker_client = None
    print("⚠️ Docker not available—containers will NOT be launched.")
print("🔍 Docker client:", "OK" if docker_client else "NOT AVAILABLE")


def ensure_network(group):
    """Create or fetch a Docker bridge network named net_<group>."""
    if not docker_client:
        return None
    net_name = f"net_{group}"
    try:
        return docker_client.networks.get(net_name)
    except NotFound:
        return docker_client.networks.create(net_name, driver="bridge")

# ----------------------------------
# Database Initialization & Persistence
# ----------------------------------
def init_db():
    conn = sqlite3.connect("cluster.db")
    c = conn.cursor()
    c.execute("""
      CREATE TABLE IF NOT EXISTS event_logs (
        id INTEGER PRIMARY KEY,
        timestamp TEXT,
        message TEXT
      )
    """)
    c.execute("""
      CREATE TABLE IF NOT EXISTS utilization_history (
        id INTEGER PRIMARY KEY,
        timestamp REAL,
        utilization REAL
      )
    """)
    c.execute("""
      CREATE TABLE IF NOT EXISTS nodes (
        node_id TEXT PRIMARY KEY,
        cpu_total INTEGER, cpu_available INTEGER,
        memory_total INTEGER, memory_available INTEGER,
        node_type TEXT, network_group TEXT,
        last_heartbeat REAL, status TEXT,
        simulate_heartbeat INTEGER,
        container_id TEXT
      )
    """)
    c.execute("""
      CREATE TABLE IF NOT EXISTS pods (
        pod_id TEXT PRIMARY KEY,
        node_id TEXT,
        cpu INTEGER, memory INTEGER,
        network_group TEXT,
        node_affinity TEXT,
        FOREIGN KEY(node_id) REFERENCES nodes(node_id)
      )
    """)
    conn.commit()
    conn.close()

def save_node_to_db(node):
    conn = sqlite3.connect("cluster.db"); c = conn.cursor()
    c.execute("""
      INSERT OR REPLACE INTO nodes VALUES (?,?,?,?,?,?,?,?,?,?,?)
    """, (
      node["node_id"],
      node["cpu_total"], node["cpu_available"],
      node["memory_total"], node["memory_available"],
      node["node_type"], node["network_group"],
      node["last_heartbeat"], node["status"],
      int(node["simulate_heartbeat"]),
      node.get("container_id")
    ))
    conn.commit(); conn.close()

def delete_node_from_db(node_id):
    conn = sqlite3.connect("cluster.db"); c = conn.cursor()
    c.execute("DELETE FROM pods WHERE node_id=?", (node_id,))
    c.execute("DELETE FROM nodes WHERE node_id=?", (node_id,))
    conn.commit(); conn.close()

def save_pod_to_db(pod, node_id):
    conn = sqlite3.connect("cluster.db"); c = conn.cursor()
    c.execute("""
      INSERT OR REPLACE INTO pods VALUES (?,?,?,?,?,?)
    """, (
      pod["pod_id"], node_id,
      pod["cpu"], pod["memory"],
      pod["network_group"],
      pod.get("node_affinity")
    ))
    conn.commit(); conn.close()

def update_pod_node_in_db(pod_id, new_node_id):
    conn = sqlite3.connect("cluster.db"); c = conn.cursor()
    c.execute("UPDATE pods SET node_id=? WHERE pod_id=?", (new_node_id, pod_id))
    conn.commit(); conn.close()

def load_cluster_state():
    conn = sqlite3.connect("cluster.db"); c = conn.cursor()
    for (nid, cpu_tot, cpu_av, mem_tot, mem_av, ntype, ngroup,
         lh, status, sim, cont_id) in c.execute("SELECT * FROM nodes"):
        nodes[nid] = {
            "node_id": nid,
            "cpu_total": cpu_tot,
            "cpu_available": cpu_av,
            "memory_total": mem_tot,
            "memory_available": mem_av,
            "node_type": ntype,
            "network_group": ngroup,
            "last_heartbeat": lh,
            "status": status,
            "simulate_heartbeat": bool(sim),
            "pods": [],
            "container_id": cont_id
        }
    for (pid, nid, cpu, mem, ng, affinity) in c.execute("""
        SELECT pod_id,node_id,cpu,memory,network_group,node_affinity FROM pods
    """):
        pod = {"pod_id": pid, "cpu": cpu, "memory": mem,
               "network_group": ng, "cpu_usage": 0}
        if affinity:
            pod["node_affinity"] = affinity
        if nid in nodes:
            nodes[nid]["pods"].append(pod)
    conn.close()

# ----------------------------------
# Global Data & Locks
# ----------------------------------
nodes               = {}
event_log           = []
utilization_history = []
nodes_lock          = RLock()
pod_id_lock         = RLock()
pod_id_counter      = 0

DEFAULT_NODE_CPU    = 8
DEFAULT_NODE_MEMORY = 16
DEFAULT_POD_MEMORY  = 4

AUTO_SCALE_THRESHOLD  = 0.8
last_auto_scale_time = 0
AUTO_SCALE_COOLDOWN   = 60
HEARTBEAT_THRESHOLD   = 15
HEALTH_CHECK_INTERVAL = 5

SCHEDULING_ALGORITHMS = ['first_fit','best_fit','worst_fit']

app = Flask(__name__)
socketio = SocketIO(app, cors_allowed_origins="*", async_mode="threading")

# ----------------------------------
# Full Dashboard HTML + JS
# ----------------------------------
advanced_dashboard_html = """
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Insane Cluster Dashboard</title>
  <!-- jQuery, Bootstrap, AdminLTE, FontAwesome, Chart.js, ECharts, Socket.IO -->
  <script src="https://code.jquery.com/jquery-3.6.0.min.js"></script>
  <script src="https://cdn.jsdelivr.net/npm/bootstrap@4.6.2/dist/js/bootstrap.bundle.min.js"></script>
  <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap@4.6.2/dist/css/bootstrap.min.css">
  <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/admin-lte@3.2/dist/css/adminlte.min.css">
  <script src="https://cdn.jsdelivr.net/npm/admin-lte@3.2/dist/js/adminlte.min.js"></script>
  <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
  <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
  <script src="https://cdn.jsdelivr.net/npm/echarts/dist/echarts.min.js"></script>
  <script src="https://cdn.jsdelivr.net/npm/echarts-gl/dist/echarts-gl.min.js"></script>
  <script src="https://cdn.socket.io/4.6.1/socket.io.min.js"></script>
  <style>
    #log-panel { height:200px; overflow-y:scroll; background:#f4f6f9; padding:10px; border:1px solid #ddd; }
    #nodeGraph { height:400px; }
    .dark-mode { background-color:#343a40!important; color:#f8f9fa!important; }
  </style>
</head>
<body class="hold-transition sidebar-mini">
  <div class="wrapper">
    <!-- Navbar -->
    <nav class="main-header navbar navbar-expand navbar-white navbar-light">
      <ul class="navbar-nav">
        <li class="nav-item"><a class="nav-link" data-widget="pushmenu" href="#"><i class="fas fa-bars"></i></a></li>
        <li class="nav-item d-none d-sm-inline-block"><a href="/dashboard" class="nav-link">Dashboard</a></li>
      </ul>
      <ul class="navbar-nav ml-auto">
        <li class="nav-item"><button id="dark-toggle" class="btn btn-outline-dark nav-link">Dark Mode</button></li>
        <li class="nav-item"><button id="chaos-btn" class="btn btn-danger nav-link">Chaos Monkey</button></li>
        <li class="nav-item"><a href="/download_report" class="btn btn-success nav-link" target="_blank">Download Report</a></li>
      </ul>
    </nav>
    <!-- Sidebar -->
    <aside class="main-sidebar sidebar-dark-primary elevation-4">
      <a href="/dashboard" class="brand-link"><i class="fas fa-server brand-image img-circle elevation-3"></i>
        <span class="brand-text font-weight-light">Insane Cluster</span>
      </a>
      <div class="sidebar"><nav class="mt-2"><ul class="nav nav-pills nav-sidebar flex-column">
        <li class="nav-item"><a href="/dashboard" class="nav-link active"><i class="nav-icon fas fa-tachometer-alt"></i><p>Dashboard</p></a></li>
      </ul></nav></div>
    </aside>
    <!-- Content Wrapper -->
    <div class="content-wrapper">
      <div class="content-header"><div class="container-fluid"><div class="row mb-2">
        <div class="col-sm-6"><h1 class="m-0">Cluster Overview</h1></div>
        <div class="col-sm-6 text-right"><button id="refresh-btn" class="btn btn-secondary">Refresh Now</button></div>
      </div></div></div>
      <section class="content"><div class="container-fluid">
        <!-- Overview Cards -->
        <div class="row">
          <div class="col-lg-4 col-6"><div class="small-box bg-info"><div class="inner"><h3 id="active-nodes">0</h3><p>Active Nodes</p></div><div class="icon"><i class="fas fa-server"></i></div></div></div>
          <div class="col-lg-4 col-6"><div class="small-box bg-success"><div class="inner"><h3 id="utilization">0%</h3><p>Cluster Utilization</p></div><div class="icon"><i class="fas fa-chart-line"></i></div></div></div>
          <div class="col-lg-4 col-6"><div class="small-box bg-warning"><div class="inner"><h3 id="total-nodes">0</h3><p>Total Nodes</p></div><div class="icon"><i class="fas fa-list"></i></div></div></div>
        </div>
        <!-- Node Table -->
        <div class="card">
          <div class="card-header"><h3 class="card-title">Node Details</h3>
            <div class="card-tools">
              <button class="btn btn-primary btn-sm" data-toggle="modal" data-target="#addNodeModal">Add Node</button>
              <button class="btn btn-primary btn-sm" data-toggle="modal" data-target="#launchPodModal">Launch Pod</button>
            </div>
          </div>
          <div class="card-body table-responsive p-0">
            <table class="table table-hover" id="nodes-table">
              <thead><tr>
                <th>Node ID</th><th>Type</th><th>CPU (Tot/Avail)</th><th>Mem (Tot/Avail)</th>
                <th>Status</th><th>Pods</th><th>Sim</th><th>Actions</th>
              </tr></thead><tbody></tbody>
            </table>
          </div>
        </div>
        <!-- Charts & Graphs -->
        <div class="row">
          <div class="col-md-6"><div class="card card-outline card-success"><div class="card-header"><h3 class="card-title">CPU Distribution</h3></div><div class="card-body"><canvas id="cpuChart" style="height:200px"></canvas></div></div></div>
          <div class="col-md-6"><div class="card card-outline card-info"><div class="card-header"><h3 class="card-title">Utilization History</h3></div><div class="card-body"><canvas id="utilChart" style="height:200px"></canvas></div></div></div>
        </div>
        <div class="card"><div class="card-header"><h3 class="card-title">3D Node Graph</h3></div><div class="card-body"><div id="nodeGraph" style="height:400px"></div></div></div>
        <div class="card"><div class="card-header"><h3 class="card-title">Event Log</h3></div><div class="card-body"><div id="log-panel"></div></div></div>
      </div></section>
    </div>
    <footer class="main-footer"><strong>&copy; 2025 Insane Cluster Dashboard.</strong> All rights reserved.</footer>
  </div>

  <!-- Modals -->
  <div class="modal fade" id="addNodeModal" tabindex="-1"><div class="modal-dialog"><div class="modal-content">
    <div class="modal-header"><h4 class="modal-title">Add Node</h4><button type="button" class="close" data-dismiss="modal">&times;</button></div>
    <div class="modal-body"><form id="addNodeForm">
      <div class="form-group"><label>CPU Cores</label><input id="cpuInput" class="form-control" required></div>
      <div class="form-group"><label>Memory (GB)</label><input id="memoryInput" class="form-control" required></div>
      <div class="form-group"><label>Node Type</label><select id="nodeTypeInput" class="form-control">
        <option value="balanced" selected>Balanced</option><option value="high_cpu">High CPU</option><option value="high_mem">High Memory</option>
      </select></div>
      <div class="form-group"><label>Network Group</label><input id="nodeGroupInput" class="form-control" placeholder="default"></div>
      <button type="submit" class="btn btn-success">Add Node</button>
    </form></div>
  </div></div></div>

  <div class="modal fade" id="launchPodModal" tabindex="-1"><div class="modal-dialog"><div class="modal-content">
    <div class="modal-header"><h4 class="modal-title">Launch Pod</h4><button type="button" class="close" data-dismiss="modal">&times;</button></div>
    <div class="modal-body"><form id="launchPodForm">
      <div class="form-group"><label>CPU Required</label><input id="cpuRequired" type="number" class="form-control" required></div>
      <div class="form-group"><label>Memory (GB)</label><input id="memoryRequired" type="number" class="form-control"></div>
      <div class="form-group"><label>Scheduling Algorithm</label><select id="schedulingAlgorithm" class="form-control">
        <option value="first_fit">First Fit</option><option value="best_fit">Best Fit</option><option value="worst_fit">Worst Fit</option>
      </select></div>
      <div class="form-group"><label>Network Group</label><input id="networkGroup" class="form-control" placeholder="default"></div>
      <div class="form-group"><label>Node Affinity</label><select id="nodeAffinity" class="form-control">
        <option value="">Any</option><option value="balanced">Balanced</option><option value="high_cpu">High CPU</option><option value="high_mem">High Memory</option>
      </select></div>
      <button type="submit" class="btn btn-primary">Launch Pod</button>
    </form></div>
  </div></div></div>

  <!-- Enhanced JS -->
  <script>
  console.log("🚀 Dashboard loaded");

  // Socket setup
  const socket = io();
  socket.on("state_update", state => {
    console.log("🔄 state_update", state);
    updateDashboard(state);
    updateNodeGraph(state.nodes);
  });

  // On connect, we get initial state. Later broadcasts keep it fresh.

  // Manual refresh
  $("#refresh-btn").click(() => location.reload());

  // Add Node
  $("#addNodeForm").submit(e => {
    e.preventDefault();
    const cpu = +$("#cpuInput").val(),
          mem = +$("#memoryInput").val(),
          type= $("#nodeTypeInput").val(),
          grp = $("#nodeGroupInput").val()||"default";
    console.log("➕ Adding node", {cpu,mem,type,grp});
    $.ajax({
      url: "/add_node", method: "POST", contentType: "application/json",
      data: JSON.stringify({cpu, memory:mem, node_type:type, network_group:grp}),
      success(res) {
        console.log("✅ add_node", res);
        $("#addNodeModal").modal("hide");
        // Immediately fetch new state
        socket.emit("connect");
      },
      error(xhr) {
        console.error("❌ add_node", xhr.responseJSON);
        alert("Error adding node: " + JSON.stringify(xhr.responseJSON));
      }
    });
  });

  // Launch Pod
  $("#launchPodForm").submit(e => {
    e.preventDefault();
    const cpuReq   = +$("#cpuRequired").val(),
          memReq   = +$("#memoryRequired").val()||4,
          algo     = $("#schedulingAlgorithm").val(),
          grp      = $("#networkGroup").val()||"default",
          affinity = $("#nodeAffinity").val()||null;
    console.log("🐳 Launch pod", {cpuReq,memReq,algo,grp,affinity});
    const payload = {
      cpu_required: cpuReq,
      memory_required: memReq,
      scheduling_algorithm: algo,
      network_group: grp
    };
    if (affinity) payload.node_affinity = affinity;
    $.ajax({
      url: "/launch_pod", method: "POST", contentType: "application/json",
      data: JSON.stringify(payload),
      success(res) {
        console.log("✅ launch_pod", res);
        $("#launchPodModal").modal("hide");
        socket.emit("connect");  // refresh state
      },
      error(xhr) {
        console.error("❌ launch_pod", xhr.responseJSON);
        alert("Error launching pod: " + JSON.stringify(xhr.responseJSON));
      }
    });
  });

  // Chaos Monkey
  $("#chaos-btn").click(() => {
    console.log("🐵 Chaos Monkey triggered");
    $.post("/chaos_monkey")
      .done(res => { console.log("✅ chaos_monkey", res); alert(res.message); socket.emit("connect"); })
      .fail(xhr => { console.error("❌ chaos_monkey", xhr.responseJSON); });
  });

  // Toggle heartbeat simulation
  $(document).on("click",".toggle-btn", function(){
    const id = $(this).data("node"), sim = $(this).data("simulate");
    console.log("🔄 toggle simulation",id,sim);
    $.ajax({
      url: "/toggle_simulation", method: "POST", contentType: "application/json",
      data: JSON.stringify({node_id: id, simulate: sim})
    })
    .done(r => { console.log("✅ toggle_simulation", r); socket.emit("connect"); })
    .fail(xhr => console.error("❌ toggle_simulation", xhr.responseJSON));
  });

  // Remove Node
  $(document).on("click",".remove-btn", function(){
    const id = $(this).data("node");
    console.log("🗑️ remove node", id);
    $.ajax({
      url: "/remove_node", method: "POST", contentType: "application/json",
      data: JSON.stringify({node_id: id})
    })
    .done(r => { console.log("✅ remove_node", r); socket.emit("connect"); })
    .fail(xhr => console.error("❌ remove_node", xhr.responseJSON));
  });

  // *** Dashboard update functions ***
  function updateDashboard(state) {
    let totalCPU=0, activeCnt=0, rows="";
    const usedCPUs=[];
    state.nodes.forEach(n=>{
      totalCPU += n.cpu_total;
      if(n.status==="active") activeCnt++;
      usedCPUs.push({node_id:n.node_id,used:(n.cpu_total-n.cpu_available)});
      // build row...
      let pods = n.pods.length
        ? n.pods.map(p=>`${p.pod_id} (CPU:${p.cpu},Mem:${p.memory})`).join("<br>")
        : "None";
      let simBtn = n.simulate_heartbeat ? "Disable" : "Enable",
          nextSim = n.simulate_heartbeat?false:true;
      rows += `
        <tr>
          <td>${n.node_id}</td>
          <td>${n.node_type}</td>
          <td>${n.cpu_total} / ${n.cpu_available}</td>
          <td>${n.memory_total} / ${n.memory_available}</td>
          <td>${n.status}</td>
          <td>${pods}</td>
          <td><button class="btn btn-info btn-sm toggle-btn" data-node="${n.node_id}" data-simulate="${nextSim}">${simBtn}</button></td>
          <td><button class="btn btn-danger btn-sm remove-btn" data-node="${n.node_id}">Remove</button></td>
        </tr>`;
    });
    $("#nodes-table tbody").html(rows);
    $("#active-nodes").text(activeCnt);
    $("#total-nodes").text(state.nodes.length);
    let utilPct = totalCPU>0
      ? Math.round((usedCPUs.reduce((a,b)=>a+b.used,0)/totalCPU)*100)
      : 0;
    $("#utilization").text(utilPct + "%");

    updatePieChart(usedCPUs);
    $("#log-panel").html(state.logs.join("<br>"));

    const times = state.history.map(h=>new Date(h.timestamp*1000).toLocaleTimeString());
    const utils = state.history.map(h=>h.utilization.toFixed(2));
    updateLineChart(times, utils);
  }

  // Pie chart
  const pieCtx = document.getElementById("cpuChart").getContext("2d"),
        cpuPieChart = new Chart(pieCtx, {
          type:"pie", data:{labels:[],datasets:[{data:[],backgroundColor:[]}]} });
  function updatePieChart(dataArr){
    let labels=[],d=[],cols=[];
    dataArr.forEach((it,i)=>{labels.push(it.node_id.slice(0,8));d.push(it.used);
      cols.push(`hsl(${(i*50)%360},70%,60%)`);
    });
    cpuPieChart.data.labels=labels;
    cpuPieChart.data.datasets[0].data=d;
    cpuPieChart.data.datasets[0].backgroundColor=cols;
    cpuPieChart.update();
  }

  // Line chart
  const lineCtx = document.getElementById("utilChart").getContext("2d"),
        utilLineChart = new Chart(lineCtx, {
          type:"line",
          data:{labels:[],datasets:[{label:"Util (%)",data:[],fill:false,tension:0.1}]}
        });
  function updateLineChart(labels, data){
    utilLineChart.data.labels=labels;
    utilLineChart.data.datasets[0].data=data;
    utilLineChart.update();
  }

  // 3D node graph
  const nodeGraphChart = echarts.init(document.getElementById("nodeGraph"));
  function updateNodeGraph(nodesData){
    const pts = nodesData.map(n=>{
      const x=Math.random()*100,y=Math.random()*100,z=Math.random()*100;
      return [x,y,z,n.node_id,n.status==="active"?"#28a745":"#dc3545"];
    });
    nodeGraphChart.setOption({
      tooltip:{formatter: p=>`Node: ${p.data[3]}<br/>(${p.data[0].toFixed(1)},${p.data[1].toFixed(1)},${p.data[2].toFixed(1)})`},
      xAxis3D:{},yAxis3D:{},zAxis3D:{},
      grid3D:{viewControl:{projection:"orthographic",autoRotate:true}},
      series:[{type:"scatter3D",symbolSize:20,data:pts,itemStyle:{color:p=>p.data[4]}}]
    });
  }
</script>

</body>
</html>
"""

# ----------------------------------
# Utility Functions
# ----------------------------------
def get_current_timestamp():
    return time.time()

def log_event_func(event):
    ts = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(get_current_timestamp()))
    entry = f"[{ts}] {event}"
    with nodes_lock:
        event_log.append(entry)
        if len(event_log) > 50:
            event_log.pop(0)
    conn = sqlite3.connect("cluster.db")
    c = conn.cursor()
    c.execute("INSERT INTO event_logs (timestamp, message) VALUES (?,?)", (ts, event))
    conn.commit()
    conn.close()

@socketio.on('connect')
def on_connect():
    with nodes_lock:
        state = {
            "nodes": list(nodes.values()),
            "logs":  event_log[-50:],
            "history": [{"timestamp": ts, "utilization": u} for ts,u in utilization_history]
        }
    emit('state_update', state)

def record_utilization():
    while True:
        time.sleep(10)
        util = get_cluster_utilization() * 100
        ts = get_current_timestamp()
        with nodes_lock:
            utilization_history.append((ts, util))
            if len(utilization_history) > 50:
                utilization_history.pop(0)
        conn = sqlite3.connect("cluster.db")
        c = conn.cursor()
        c.execute("INSERT INTO utilization_history (timestamp, utilization) VALUES (?,?)", (ts, util))
        conn.commit()
        conn.close()

@socketio.on('connect')
def handle_connect():
    # Send the current full state immediately on new client connection
    with nodes_lock:
        state = {
            "nodes": list(nodes.values()),
            "logs":  event_log[-50:],
            "history": [
                {"timestamp": ts, "utilization": util}
                for ts, util in utilization_history
            ]
        }
    emit('state_update', state)

def get_cluster_utilization():
    total = used = 0
    with nodes_lock:
        for n in nodes.values():
            if n["status"] == "active":
                total += n["cpu_total"]
                used += (n["cpu_total"] - n["cpu_available"])
    return 0.0 if total == 0 else used / total

# ----------------------------------
# Scheduling & Pod Persistence
# ----------------------------------
def schedule_pod(pod, algo):
    with nodes_lock:
        eligible = [
            n for n in nodes.values()
            if n["status"] == "active"
               and n["cpu_available"] >= pod["cpu"]
               and n["memory_available"] >= pod["memory"]
               and n["network_group"] == pod["network_group"]
        ]
        if "node_affinity" in pod:
            eligible = [n for n in eligible if n["node_type"] == pod["node_affinity"]]
        if not eligible:
            return False, None
        if algo == "first_fit":
            cand = eligible[0]
        elif algo == "best_fit":
            cand = min(eligible, key=lambda n: (n["cpu_available"] - pod["cpu"]) + (n["memory_available"] - pod["memory"]))
        else:  # worst_fit
            cand = max(eligible, key=lambda n: n["cpu_available"] + n["memory_available"])
        cand["pods"].append(pod)
        cand["cpu_available"]   -= pod["cpu"]
        cand["memory_available"]-= pod["memory"]
        save_node_to_db(cand)
        log_event_func(f"Pod {pod['pod_id']} scheduled on node {cand['node_id']} via {algo}")
        return True, cand["node_id"]

def reschedule_pods_from_failed_node(nid):
    with nodes_lock:
        failed = nodes.pop(nid, None)
    if not failed:
        return
    delete_node_from_db(nid)
    for pod in failed["pods"]:
        ok, new_nid = schedule_pod(pod, "first_fit")
        if ok:
            update_pod_node_in_db(pod["pod_id"], new_nid)
            log_event_func(f"Rescheduled pod {pod['pod_id']} → {new_nid}")
        else:
            log_event_func(f"Failed to reschedule pod {pod['pod_id']}")

# ----------------------------------
# Health Monitor & Heartbeats
# ----------------------------------
def health_monitor():
    while True:
        time.sleep(HEALTH_CHECK_INTERVAL)
        now = get_current_timestamp()
        to_fail = []
        with nodes_lock:
            for nid, n in list(nodes.items()):
                if n["status"] == "active" and (now - n["last_heartbeat"]) > HEARTBEAT_THRESHOLD:
                    n["status"] = "failed"
                    save_node_to_db(n)
                    log_event_func(f"Node {nid} marked FAILED")
                    to_fail.append(nid)
        for nid in to_fail:
            socketio.emit("alert", {"msg": f"Node {nid} failed"})
            reschedule_pods_from_failed_node(nid)

def simulate_heartbeat_thread():
    while True:
        time.sleep(NODE_HEARTBEAT_INTERVAL)
        with nodes_lock:
            for n in nodes.values():
                if n["simulate_heartbeat"]:
                    n["last_heartbeat"] = get_current_timestamp()
                    save_node_to_db(n)

# ----------------------------------
# Auto‐scaling with Docker & Persistence
# ----------------------------------
def auto_scale_cluster():
    global last_auto_scale_time
    while True:
        time.sleep(HEALTH_CHECK_INTERVAL)
        util = get_cluster_utilization()
        now = get_current_timestamp()
        if util >= AUTO_SCALE_THRESHOLD and (now - last_auto_scale_time) >= AUTO_SCALE_COOLDOWN:
            nid = str(uuid.uuid4())
            nt = random.choice(["high_cpu","high_mem","balanced"])
            ng = random.choice(["default","isolated"])
            node = {
                "node_id": nid,
                "cpu_total": DEFAULT_NODE_CPU,
                "cpu_available": DEFAULT_NODE_CPU,
                "memory_total": DEFAULT_NODE_MEMORY,
                "memory_available": DEFAULT_NODE_MEMORY,
                "node_type": nt,
                "network_group": ng,
                "pods": [],
                "last_heartbeat": now,
                "status": "active",
                "simulate_heartbeat": True
            }
            with nodes_lock:
                nodes[nid] = node
            save_node_to_db(node)
            net = ensure_network(ng)
            if docker_client and net:
                try:
                    cont = docker_client.containers.run(
                        DOCKER_NODE_IMAGE,
                        entrypoint=["python", "node.py"],
                        command=[
                            "python","node.py",
                            "--server","http://host.docker.internal:5000",
                            "--node_id",nid,
                            "--interval",str(NODE_HEARTBEAT_INTERVAL)
                        ],
                        name=f"node_{nid}",
                        detach=True,
                        network=net.name,
                        cpu_count=DEFAULT_NODE_CPU,
                        mem_limit=f"{DEFAULT_NODE_MEMORY}g",
                        labels={"sim-node": nid, "autoscaled": "true"},
                        remove = True 
                    )
                    nodes[nid]["container_id"] = cont.id
                    save_node_to_db(nodes[nid])
                    log_event_func(f"Container {cont.id[:12]} launched for auto‐scaled node {nid}")
                except Exception as e:
                    log_event_func(f"Auto‐scale container error for {nid}: {e}")
            else:
                log_event_func(f"Skipping container launch for auto‐scaled node {nid}")
            log_event_func(f"Auto‐scaled: Added node {nid} ({DEFAULT_NODE_CPU} CPU, {DEFAULT_NODE_MEMORY}GB, Type:{nt}, Group:{ng})")
            last_auto_scale_time = now

# ----------------------------------
# Chaos Monkey & Broadcast
# ----------------------------------
def chaos_monkey():
    with nodes_lock:
        active = [n for n in nodes.values() if n["status"]=="active"]
    if not active:
        return {"message":"No active nodes"}
    target = random.choice(active)
    target["status"] = "failed"
    save_node_to_db(target)
    log_event_func(f"Chaos Monkey killed node {target['node_id']}")
    reschedule_pods_from_failed_node(target["node_id"])
    return {"message":f"Killed node {target['node_id']}"}

def broadcast_state():
    while True:
        time.sleep(3)
        with nodes_lock:
            state = {
                "nodes": list(nodes.values()),
                "logs": event_log[-50:],
                "history": [{"timestamp": ts, "utilization": util} for ts, util in utilization_history]
            }
        socketio.emit("state_update", state)

# ----------------------------------
# API Endpoints
# ----------------------------------
@app.route('/add_node', methods=['POST'])
def add_node_endpoint():
    data = request.get_json() or {}
    print("▶️  /add_node called with:", data)

    cpu = data.get("cpu")
    if cpu is None:
        print("❌  Missing cpu in payload")
        return jsonify({"error":"Missing cpu"}), 400
    mem = data.get("memory", DEFAULT_NODE_MEMORY)
    nt  = data.get("node_type", "balanced")
    ng  = data.get("network_group", "default")

    # 1) create node record
    node_id = str(uuid.uuid4())
    node = {
        "node_id": node_id,
        "cpu_total": cpu, "cpu_available": cpu,
        "memory_total": mem, "memory_available": mem,
        "node_type": nt, "network_group": ng,
        "pods": [], "last_heartbeat": time.time(),
        "status": "active", "simulate_heartbeat": True
    }
    with nodes_lock:
        nodes[node_id] = node
    save_node_to_db(node)
    log_event_func(f"Added node {node_id} ({cpu} CPU, {mem}GB, {nt}/{ng})")

    # 2) launch container
    if docker_client:
        server_url = "http://host.docker.internal:5000"
        print(f"⚙️  Launching container for {node_id} on network '{ng}' via {server_url}")
        net = ensure_network(ng)
        try:
            container = docker_client.containers.run(
                DOCKER_NODE_IMAGE,
                entrypoint= ["python", "node.py"],
                command=[
                  "python", "node.py",
                  "--server", server_url,
                  "--node_id", node_id,
                  "--interval", str(NODE_HEARTBEAT_INTERVAL)
                ],
                name=f"node_{node_id}",
                detach=True,
                network=net.name if net else None,
                cpu_count=cpu,
                mem_limit=f"{mem}g",
                labels={"sim-node": node_id},
                auto_remove = False
            )
            print("✅ Container started:", container.id)
            with nodes_lock:
                nodes[node_id]["container_id"] = container.id
            save_node_to_db(nodes[node_id])
            log_event_func(f"Container {container.id[:12]} launched for node {node_id}")
        except Exception as ex:
            print("❌ Container launch error:", ex)
            log_event_func(f"ERROR launching container for node {node_id}: {ex}")
    else:
        print("⚠️  Skipping container launch (no docker_client)")

    return jsonify({"message":"Node added","node_id":node_id}), 200


@app.route('/toggle_simulation', methods=['POST'])
def toggle_simulation():
    data = request.get_json()
    nid, sim = data.get("node_id"), bool(data.get("simulate"))
    if not nid:
        return jsonify({"error":"Missing node_id"}),400
    with nodes_lock:
        n = nodes.get(nid)
        if not n:
            return jsonify({"error":"Not found"}),404
        n["simulate_heartbeat"] = sim
        save_node_to_db(n)
    log_event_func(f"Simulation for {nid} set to {sim}")
    return jsonify({"message":"OK"}),200

@app.route('/list_nodes', methods=['GET'])
def list_nodes_api():
    with nodes_lock:
        return jsonify({"nodes": list(nodes.values())}),200

@app.route('/heartbeat', methods=['POST'])
def heartbeat_api():
    data = request.get_json() or {}
    nid = data.get("node_id")
    with nodes_lock:
        n = nodes.get(nid)
        if not n:
            return jsonify({"error":"Unknown"}),404
        n["last_heartbeat"] = time.time()
        if n["status"] == "failed":
            n["status"] = "active"
            save_node_to_db(n)
            log_event_func(f"Node {nid} reactivated")
    return jsonify({"message":"OK"}),200
@app.route('/launch_pod', methods=['POST'])
def launch_pod_endpoint():
    data = request.get_json() or {}
    print("▶️  /launch_pod called with:", data)

    cpu_req = data.get("cpu_required")
    if cpu_req is None:
        print("❌  Missing cpu_required")
        return jsonify({"error":"Missing cpu_required"}), 400

    mem_req = data.get("memory_required", DEFAULT_POD_MEMORY)
    algo    = data.get("scheduling_algorithm", "first_fit").lower()
    ng      = data.get("network_group", "default")
    affinity= data.get("node_affinity")

    global pod_id_counter
    with pod_id_lock:
        pod_id_counter += 1
        pid = f"pod_{pod_id_counter}"

    pod = {
        "pod_id": pid,
        "cpu": cpu_req,
        "memory": mem_req,
        "network_group": ng,
        "cpu_usage": 0
    }
    if affinity:
        pod["node_affinity"] = affinity

    scheduled, assigned = schedule_pod(pod, algo)
    if scheduled:
        save_pod_to_db(pod, assigned)
        print(f"✅ Pod {pid} scheduled on node {assigned} via {algo}")
        return jsonify({
            "message": "Pod launched",
            "pod_id": pid,
            "assigned_node": assigned,
            "scheduling_algorithm": algo
        }), 200
    else:
        print(f"❌ No capacity for pod {pid}")
        return jsonify({"error": "No available node with sufficient resources"}), 400


@app.route('/chaos_monkey', methods=['POST'])
def chaos_api():
    return jsonify(chaos_monkey()),200

@app.route('/download_report', methods=['GET'])
def download_report():
    out = io.StringIO(); w = csv.writer(out)
    w.writerow(["Node","CPU tot/avail","Mem tot/avail","Status","Type","Group","Pods"])
    with nodes_lock:
        for n in nodes.values():
            pods = ";".join(p["pod_id"] for p in n["pods"]) or "None"
            w.writerow([
                n["node_id"],
                f"{n['cpu_total']}/{n['cpu_available']}",
                f"{n['memory_total']}/{n['memory_available']}",
                n["status"], n["node_type"], n["network_group"], pods
            ])
    out.seek(0)
    return send_file(io.BytesIO(out.getvalue().encode()),
                     mimetype="text/csv",
                     as_attachment=True,
                     download_name="cluster_report.csv")

@app.route('/logs', methods=['GET'])
def logs_api():
    with nodes_lock:
        return jsonify({"logs": event_log}),200

@app.route('/utilization_history', methods=['GET'])
def util_api():
    with nodes_lock:
        hist = [{"timestamp": ts, "utilization": util} for ts, util in utilization_history]
    return jsonify({"history": hist}),200

@app.route('/dashboard')
def dashboard():
    return render_template_string(advanced_dashboard_html)

# ----------------------------------
# Background Tasks & Startup
# ----------------------------------
def background_tasks():
    Thread(target=health_monitor, daemon=True).start()
    Thread(target=simulate_heartbeat_thread, daemon=True).start()
    Thread(target=auto_scale_cluster, daemon=True).start()
    Thread(target=record_utilization, daemon=True).start()
    Thread(target=broadcast_state, daemon=True).start()

if __name__ == '__main__':
    init_db()
    load_cluster_state()
    background_tasks()
    socketio.run(app, host="0.0.0.0", port=5000, debug=True)
