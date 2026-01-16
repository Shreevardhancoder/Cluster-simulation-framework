// Using Material UI Components
const {
  AppBar, Toolbar, Typography, Container, Grid, Paper, Button, IconButton,
  Dialog, DialogTitle, DialogContent, DialogActions, TextField, MenuItem,
  Switch, FormControlLabel, Chip, Snackbar, CircularProgress, Drawer, List,
  ListItem, ListItemIcon, ListItemText, Divider, Card, CardContent, CardActions,
  Tab, Tabs
} = MaterialUI;

// Socket.io client connection
const socket = io();

// Main App Component
const App = () => {
  const [nodes, setNodes] = React.useState([]);
  const [logs, setLogs] = React.useState([]);
  const [darkMode, setDarkMode] = React.useState(false);
  const [openNodeDialog, setOpenNodeDialog] = React.useState(false);
  const [openPodDialog, setOpenPodDialog] = React.useState(false);
  const [notification, setNotification] = React.useState({ open: false, message: '' });
  const [drawerOpen, setDrawerOpen] = React.useState(false);
  const [currentTab, setCurrentTab] = React.useState(0);
  const [nodeForm, setNodeForm] = React.useState({
    cpu: 8,
    memory: 16,
    node_type: 'balanced',
    network_group: 'default'
  });
  const [podForm, setPodForm] = React.useState({
    cpu_required: 2,
    memory_required: 4,
    scheduling_algorithm: 'first_fit',
    network_group: 'default',
    node_affinity: ''
  });

  React.useEffect(() => {
    // Listen for state updates from socket
    socket.on("state_update", (state) => {
      setNodes(state.nodes || []);
      setLogs(state.logs || []);
    });
    
    // Listen for alerts
    socket.on("alert", (data) => {
      showNotification(data.msg);
    });
    
    // Apply dark mode to body
    if (darkMode) {
      document.body.classList.add('dark-mode');
    } else {
      document.body.classList.remove('dark-mode');
    }
    
    return () => {
      socket.off("state_update");
      socket.off("alert");
    };
  }, [darkMode]);

  const addNode = async () => {
    try {
      const response = await fetch('/api/add_node', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(nodeForm)
      });
      
      if (!response.ok) throw new Error('Failed to add node');
      
      const data = await response.json();
      showNotification(`Node ${data.node_id} added successfully`);
      setOpenNodeDialog(false);
    } catch (error) {
      showNotification(`Error: ${error.message}`);
    }
  };

  const launchPod = async () => {
    try {
      const response = await fetch('/api/launch_pod', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(podForm)
      });
      
      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.error || 'Failed to launch pod');
      }
      
      const data = await response.json();
      showNotification(`Pod ${data.pod_id} launched on node ${data.assigned_node}`);
      setOpenPodDialog(false);
    } catch (error) {
      showNotification(`Error: ${error.message}`);
    }
  };

  const removeNode = async (nodeId) => {
    try {
      const response = await fetch('/api/remove_node', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ node_id: nodeId })
      });
      
      if (!response.ok) throw new Error('Failed to remove node');
      
      showNotification(`Node ${nodeId} removed`);
    } catch (error) {
      showNotification(`Error: ${error.message}`);
    }
  };

  const toggleSimulation = async (nodeId, simulate) => {
    console.log(`Toggling simulation for node ${nodeId} to ${simulate}`);
    try {
      const response = await fetch('/api/toggle_simulation', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ node_id: nodeId, simulate })
      });
      const data = await response.json();
      console.log('Toggle simulation response:', data);
      showNotification(`Heartbeat simulation ${simulate ? 'enabled' : 'disabled'} for node ${nodeId}`);
    } catch (error) {
      console.error('Error toggling simulation:', error);
      showNotification(`Error: ${error.message}`);
    }
  };

  const triggerChaosMonkey = async () => {
    try {
      const response = await fetch('/api/chaos_monkey', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' }
      });
      
      if (!response.ok) throw new Error('Failed to trigger Chaos Monkey');
      
      const data = await response.json();
      showNotification(data.message);
    } catch (error) {
      showNotification(`Error: ${error.message}`);
    }
  };
  
  const downloadReport = () => {
    window.open('/api/download_report', '_blank');
  };

  const handleNodeFormChange = (e) => {
    const { name, value } = e.target;
    setNodeForm({ ...nodeForm, [name]: name === 'cpu' || name === 'memory' ? parseInt(value) : value });
  };

  const handlePodFormChange = (e) => {
    const { name, value } = e.target;
    setPodForm({ 
      ...podForm, 
      [name]: name === 'cpu_required' || name === 'memory_required' ? parseInt(value) : value 
    });
  };

  const showNotification = (message) => {
    setNotification({ open: true, message });
  };

  const closeNotification = () => {
    setNotification({ ...notification, open: false });
  };

  const getClusterStats = () => {
    const activeNodes = nodes.filter(n => n.status === "active").length;
    const totalCpu = nodes.reduce((acc, n) => acc + n.cpu_total, 0);
    const availableCpu = nodes.reduce((acc, n) => acc + n.cpu_available, 0);
    const usedCpu = totalCpu - availableCpu;
    const utilization = totalCpu > 0 ? (usedCpu / totalCpu) * 100 : 0;
    
    const totalPods = nodes.reduce((acc, n) => acc + n.pods.length, 0);
    
    return {
      activeNodes,
      totalNodes: nodes.length,
      utilization: utilization.toFixed(1),
      totalPods
    };
  };

  const stats = getClusterStats();

  const triggerNodeFailure = async (nodeId) => {
    try {
      const response = await fetch('/api/chaos_monkey', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ node_id: nodeId })
      });
      
      if (!response.ok) throw new Error('Failed to fail node');
      
      const data = await response.json();
      showNotification(data.message || `Node ${nodeId} failed`);
    } catch (error) {
      showNotification(`Error: ${error.message}`);
    }
  };

  return (
    <div className="cluster-dashboard">
      {/* App Bar */}
      <AppBar position="static" className="header" color={darkMode ? "default" : "primary"}>
        <Toolbar>
          <IconButton 
            edge="start" 
            color="inherit" 
            onClick={() => setDrawerOpen(true)}
          >
            <span className="material-icons">menu</span>
          </IconButton>
          <Typography variant="h6" style={{ flexGrow: 1, marginLeft: '12px' }}>
            Distributed Cluster Management
          </Typography>
          <FormControlLabel
            control={
              <Switch 
                checked={darkMode} 
                onChange={() => setDarkMode(!darkMode)}
                color="default"
              />
            }
            label="Dark Mode"
          />
          <Button 
            color="inherit" 
            startIcon={<span className="material-icons">warning</span>}
            onClick={triggerChaosMonkey}
          >
            Chaos Monkey
          </Button>
        </Toolbar>
      </AppBar>
      
      {/* Navigation Drawer */}
      <Drawer
        anchor="left"
        open={drawerOpen}
        onClose={() => setDrawerOpen(false)}
      >
        <List style={{ width: 250 }}>
          <ListItem>
            <Typography variant="h6">Cluster Dashboard</Typography>
          </ListItem>
          <Divider />
          <ListItem button onClick={() => { setCurrentTab(0); setDrawerOpen(false); }}>
            <ListItemIcon><span className="material-icons">dashboard</span></ListItemIcon>
            <ListItemText primary="Overview" />
          </ListItem>
          <ListItem button onClick={() => { setCurrentTab(1); setDrawerOpen(false); }}>
            <ListItemIcon><span className="material-icons">storage</span></ListItemIcon>
            <ListItemText primary="Nodes" />
          </ListItem>
          <ListItem button onClick={() => { setCurrentTab(2); setDrawerOpen(false); }}>
            <ListItemIcon><span className="material-icons">view_in_ar</span></ListItemIcon>
            <ListItemText primary="Pods" />
          </ListItem>
          <ListItem button onClick={() => { setCurrentTab(3); setDrawerOpen(false); }}>
            <ListItemIcon><span className="material-icons">article</span></ListItemIcon>
            <ListItemText primary="Logs" />
          </ListItem>
          <Divider />
          <ListItem button onClick={() => setOpenNodeDialog(true)}>
            <ListItemIcon><span className="material-icons">add_circle</span></ListItemIcon>
            <ListItemText primary="Add Node" />
          </ListItem>
          <ListItem button onClick={() => setOpenPodDialog(true)}>
            <ListItemIcon><span className="material-icons">add_box</span></ListItemIcon>
            <ListItemText primary="Launch Pod" />
          </ListItem>
          <Divider />
          <ListItem button onClick={downloadReport}>
            <ListItemIcon><span className="material-icons">download</span></ListItemIcon>
            <ListItemText primary="Download Report" />
          </ListItem>
        </List>
      </Drawer>
      
      {/* Main Content */}
      <Container className="main-container">
        <Tabs 
          value={currentTab} 
          onChange={(e, newValue) => setCurrentTab(newValue)}
          style={{ marginBottom: 20 }}
        >
          <Tab label="Overview" />
          <Tab label="Nodes" />
          <Tab label="Pods" />
          <Tab label="Logs" />
        </Tabs>
        
        {/* Tab Content */}
        {currentTab === 0 && (
          <div className="slide-up">
            <Grid container spacing={3}>
              {/* Overview Stats */}
              <Grid item xs={12} md={6} lg={3}>
                <Paper className="resource-card card">
                  <span className="material-icons resource-icon">storage</span>
                  <Typography variant="h3" className="metric-value">{stats.activeNodes}</Typography>
                  <Typography variant="subtitle1" className="metric-label">Active Nodes</Typography>
                </Paper>
              </Grid>
              <Grid item xs={12} md={6} lg={3}>
                <Paper className="resource-card card">
                  <span className="material-icons resource-icon">view_in_ar</span>
                  <Typography variant="h3" className="metric-value">{stats.totalPods}</Typography>
                  <Typography variant="subtitle1" className="metric-label">Total Pods</Typography>
                </Paper>
              </Grid>
              <Grid item xs={12} md={6} lg={3}>
                <Paper className="resource-card card">
                  <span className="material-icons resource-icon">speed</span>
                  <Typography 
                    variant="h3" 
                    className="metric-value"
                    style={{ color: parseFloat(stats.utilization) > 80 ? '#f44336' : '#4caf50' }}
                  >
                    {stats.utilization}%
                  </Typography>
                  <Typography variant="subtitle1" className="metric-label">Cluster Utilization</Typography>
                </Paper>
              </Grid>
              <Grid item xs={12} md={6} lg={3}>
                <Paper className="resource-card card">
                  <span className="material-icons resource-icon">lan</span>
                  <Typography variant="h3" className="metric-value">{stats.totalNodes}</Typography>
                  <Typography variant="subtitle1" className="metric-label">Total Nodes</Typography>
                </Paper>
              </Grid>
              
              {/* Action Cards */}
              <Grid item xs={12}>
                <Grid container spacing={3}>
                  <Grid item xs={12} md={4}>
                    <Paper className="card">
                      <Typography variant="h6" className="card-title">
                        <span className="material-icons">add_circle</span> Add Node
                      </Typography>
                      <Typography variant="body2" style={{ marginBottom: 16 }}>
                        Add a new node to the cluster with specified resources.
                      </Typography>
                      <Button 
                        variant="contained" 
                        color="primary"
                        startIcon={<span className="material-icons">add</span>}
                        onClick={() => setOpenNodeDialog(true)}
                        fullWidth
                      >
                        Add Node
                      </Button>
                    </Paper>
                  </Grid>
                  <Grid item xs={12} md={4}>
                    <Paper className="card">
                      <Typography variant="h6" className="card-title">
                        <span className="material-icons">view_in_ar</span> Launch Pod
                      </Typography>
                      <Typography variant="body2" style={{ marginBottom: 16 }}>
                        Deploy a new pod with required resources to the cluster.
                      </Typography>
                      <Button 
                        variant="contained" 
                        color="primary"
                        startIcon={<span className="material-icons">play_arrow</span>}
                        onClick={() => setOpenPodDialog(true)}
                        fullWidth
                      >
                        Launch Pod
                      </Button>
                    </Paper>
                  </Grid>
                  <Grid item xs={12} md={4}>
                    <Paper className="card">
                      <Typography variant="h6" className="card-title">
                        <span className="material-icons">warning</span> Chaos Testing
                      </Typography>
                      <Typography variant="body2" style={{ marginBottom: 16 }}>
                        Test cluster resilience by randomly failing a node.
                      </Typography>
                      <Button 
                        variant="contained" 
                        color="secondary"
                        startIcon={<span className="material-icons">flash_on</span>}
                        onClick={triggerChaosMonkey}
                        fullWidth
                      >
                        Trigger Chaos Monkey
                      </Button>
                    </Paper>
                  </Grid>
                </Grid>
              </Grid>
              
              {/* Recent Logs */}
              <Grid item xs={12}>
                <Paper className="card">
                  <Typography variant="h6" className="card-title">
                    <span className="material-icons">article</span> Recent Events
                  </Typography>
                  <div className="log-panel">
                    {logs.map((log, index) => (
                      <div key={index}>{log}</div>
                    ))}
                  </div>
                </Paper>
              </Grid>
            </Grid>
          </div>
        )}
        
        {/* Nodes Tab */}
        {currentTab === 1 && (
          <div className="slide-up">
            <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 20 }}>
              <Typography variant="h5">Cluster Nodes</Typography>
              <Button 
                variant="contained" 
                color="primary"
                startIcon={<span className="material-icons">add</span>}
                onClick={() => setOpenNodeDialog(true)}
              >
                Add Node
              </Button>
            </div>
            
            <div>
              {nodes.map(node => (
                <Card 
                  key={node.node_id} 
                  className={`node-card ${node.status}`}
                  style={{ marginBottom: 16 }}
                >
                  <CardContent>
                    <div className="node-header">
                      <div>
                        <Typography variant="h6" className="node-id">
                          {node.node_id}
                        </Typography>
                        <div>
                          <Chip 
                            label={node.status.toUpperCase()} 
                            color={node.status === "active" ? "primary" : "secondary"} 
                            size="small"
                            style={{ marginRight: 8 }}
                          />
                          <Chip 
                            label={node.node_type} 
                            variant="outlined" 
                            size="small"
                            style={{ marginRight: 8 }}
                          />
                          <Chip 
                            label={`Group: ${node.network_group}`} 
                            variant="outlined" 
                            size="small"
                          />
                        </div>
                      </div>
                      <div className="node-actions">
                        <Button
                          variant="outlined"
                          color="secondary"
                          size="small"
                          onClick={() => triggerNodeFailure(node.node_id)}
                        >
                          Fail Node
                        </Button>
                        <Button
                          variant="outlined"
                          color="secondary"
                          size="small"
                          onClick={() => removeNode(node.node_id)}
                        >
                          Remove
                        </Button>
                      </div>
                    </div>
                    
                    <div className="node-details">
                      <div className="node-stat">
                        <span className="node-stat-label">CPU Total</span>
                        <span className="node-stat-value">{node.cpu_total} cores</span>
                      </div>
                      <div className="node-stat">
                        <span className="node-stat-label">CPU Available</span>
                        <span className="node-stat-value">{node.cpu_available} cores</span>
                      </div>
                      <div className="node-stat">
                        <span className="node-stat-label">Memory Total</span>
                        <span className="node-stat-value">{node.memory_total} GB</span>
                      </div>
                      <div className="node-stat">
                        <span className="node-stat-label">Memory Available</span>
                        <span className="node-stat-value">{node.memory_available} GB</span>
                      </div>
                    </div>
                    
                    <div>
                      <Typography variant="subtitle2" style={{ marginBottom: 8 }}>
                        Pods ({node.pods.length}):
                      </Typography>
                      <div>
                        {node.pods.map(pod => (
                          <Chip 
                            key={pod.pod_id}
                            label={`${pod.pod_id} (CPU:${pod.cpu}, Mem:${pod.memory})`}
                            size="small"
                            style={{ margin: '0 4px 4px 0' }}
                          />
                        ))}
                        {node.pods.length === 0 && <span style={{ fontSize: 14, opacity: 0.7 }}>No pods</span>}
                      </div>
                    </div>
                  </CardContent>
                </Card>
              ))}
              {nodes.length === 0 && (
                <div style={{ textAlign: 'center', padding: 40 }}>
                  <span className="material-icons" style={{ fontSize: 48, opacity: 0.3 }}>cloud_off</span>
                  <Typography variant="h6" style={{ opacity: 0.5 }}>No nodes available</Typography>
                  <Button 
                    variant="contained" 
                    color="primary"
                    style={{ marginTop: 16 }}
                    onClick={() => setOpenNodeDialog(true)}
                  >
                    Add Your First Node
                  </Button>
                </div>
              )}
            </div>
          </div>
        )}
        
        {/* Pods Tab */}
        {currentTab === 2 && (
          <div className="slide-up">
            <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 20 }}>
              <Typography variant="h5">Cluster Pods</Typography>
              <Button 
                variant="contained" 
                color="primary"
                startIcon={<span className="material-icons">add</span>}
                onClick={() => setOpenPodDialog(true)}
              >
                Launch Pod
              </Button>
            </div>
            
            <Grid container spacing={3}>
              {nodes.flatMap(node => 
                node.pods.map(pod => (
                  <Grid item xs={12} sm={6} md={4} key={pod.pod_id}>
                    <Paper className="card">
                      <Typography variant="h6" className="card-title">
                        <span className="material-icons">view_in_ar</span> {pod.pod_id}
                      </Typography>
                      <div style={{ marginBottom: 16 }}>
                        <Chip 
                          label={`Assigned to: ${node.node_id.substr(0, 8)}...`}
                          color="primary"
                          size="small"
                          style={{ marginRight: 8, marginBottom: 8 }}
                        />
                        <Chip 
                          label={`Network: ${pod.network_group}`}
                          variant="outlined"
                          size="small"
                          style={{ marginBottom: 8 }}
                        />
                        {pod.node_affinity && (
                          <Chip 
                            label={`Affinity: ${pod.node_affinity}`}
                            variant="outlined"
                            size="small"
                            style={{ marginBottom: 8 }}
                          />
                        )}
                      </div>
                      <div className="node-details">
                        <div className="node-stat">
                          <span className="node-stat-label">CPU</span>
                          <span className="node-stat-value">{pod.cpu} cores</span>
                        </div>
                        <div className="node-stat">
                          <span className="node-stat-label">Memory</span>
                          <span className="node-stat-value">{pod.memory} GB</span>
                        </div>
                      </div>
                    </Paper>
                  </Grid>
                ))
              )}
              {nodes.reduce((acc, node) => acc + node.pods.length, 0) === 0 && (
                <Grid item xs={12}>
                  <div style={{ textAlign: 'center', padding: 40 }}>
                    <span className="material-icons" style={{ fontSize: 48, opacity: 0.3 }}>inbox</span>
                    <Typography variant="h6" style={{ opacity: 0.5 }}>No pods running</Typography>
                    <Button 
                      variant="contained" 
                      color="primary"
                      style={{ marginTop: 16 }}
                      onClick={() => setOpenPodDialog(true)}
                    >
                      Launch Your First Pod
                    </Button>
                  </div>
                </Grid>
              )}
            </Grid>
          </div>
        )}
        
        {/* Logs Tab */}
        {currentTab === 3 && (
          <div className="slide-up">
            <Paper className="card">
              <Typography variant="h6" className="card-title">
                <span className="material-icons">article</span> Event Logs
              </Typography>
              <div className="log-panel" style={{ height: 'calc(100vh - 250px)' }}>
                {logs.map((log, index) => (
                  <div key={index} style={{ marginBottom: 4 }}>{log}</div>
                ))}
                {logs.length === 0 && (
                  <div style={{ textAlign: 'center', padding: 20 }}>
                    <Typography variant="body2" style={{ opacity: 0.5 }}>No event logs yet</Typography>
                  </div>
                )}
              </div>
              <div style={{ display: 'flex', justifyContent: 'flex-end', marginTop: 16 }}>
                <Button 
                  variant="outlined"
                  onClick={downloadReport}
                  startIcon={<span className="material-icons">download</span>}
                >
                  Download Report
                </Button>
              </div>
            </Paper>
          </div>
        )}
      </Container>
      
      {/* Add Node Dialog */}
      <Dialog open={openNodeDialog} onClose={() => setOpenNodeDialog(false)}>
        <DialogTitle>Add Node</DialogTitle>
        <DialogContent>
          <TextField
            label="CPU Cores"
            name="cpu"
            type="number"
            value={nodeForm.cpu}
            onChange={handleNodeFormChange}
            fullWidth
            margin="normal"
          />
          <TextField
            label="Memory (GB)"
            name="memory"
            type="number"
            value={nodeForm.memory}
            onChange={handleNodeFormChange}
            fullWidth
            margin="normal"
          />
          <TextField
            label="Node Type"
            name="node_type"
            select
            value={nodeForm.node_type}
            onChange={handleNodeFormChange}
            fullWidth
            margin="normal"
          >
            <MenuItem value="balanced">Balanced</MenuItem>
            <MenuItem value="high_cpu">High CPU</MenuItem>
            <MenuItem value="high_mem">High Memory</MenuItem>
          </TextField>
          <TextField
            label="Network Group"
            name="network_group"
            value={nodeForm.network_group}
            onChange={handleNodeFormChange}
            fullWidth
            margin="normal"
          />
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setOpenNodeDialog(false)} color="primary">
            Cancel
          </Button>
          <Button onClick={addNode} color="primary" variant="contained">
            Add Node
          </Button>
        </DialogActions>
      </Dialog>
      
      {/* Launch Pod Dialog */}
      <Dialog open={openPodDialog} onClose={() => setOpenPodDialog(false)}>
        <DialogTitle>Launch Pod</DialogTitle>
        <DialogContent>
          <TextField
            label="CPU Required"
            name="cpu_required"
            type="number"
            value={podForm.cpu_required}
            onChange={handlePodFormChange}
            fullWidth
            margin="normal"
          />
          <TextField
            label="Memory Required (GB)"
            name="memory_required"
            type="number"
            value={podForm.memory_required}
            onChange={handlePodFormChange}
            fullWidth
            margin="normal"
          />
          <TextField
            label="Scheduling Algorithm"
            name="scheduling_algorithm"
            select
            value={podForm.scheduling_algorithm}
            onChange={handlePodFormChange}
            fullWidth
            margin="normal"
          >
            <MenuItem value="first_fit">First Fit</MenuItem>
            <MenuItem value="best_fit">Best Fit</MenuItem>
            <MenuItem value="worst_fit">Worst Fit</MenuItem>
          </TextField>
          <TextField
            label="Network Group"
            name="network_group"
            value={podForm.network_group}
            onChange={handlePodFormChange}
            fullWidth
            margin="normal"
          />
          <TextField
            label="Node Affinity (Optional)"
            name="node_affinity"
            select
            value={podForm.node_affinity}
            onChange={handlePodFormChange}
            fullWidth
            margin="normal"
          >
            <MenuItem value="">No Affinity</MenuItem>
            <MenuItem value="balanced">Balanced</MenuItem>
            <MenuItem value="high_cpu">High CPU</MenuItem>
            <MenuItem value="high_mem">High Memory</MenuItem>
          </TextField>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setOpenPodDialog(false)} color="primary">
            Cancel
          </Button>
          <Button onClick={launchPod} color="primary" variant="contained">
            Launch Pod
          </Button>
        </DialogActions>
      </Dialog>
      
      {/* Notification Snackbar */}
      <Snackbar
        open={notification.open}
        autoHideDuration={6000}
        onClose={closeNotification}
        message={notification.message}
        action={
          <IconButton size="small" color="inherit" onClick={closeNotification}>
            <span className="material-icons">close</span>
          </IconButton>
        }
      />
    </div>
  );
};

// Render the App
ReactDOM.render(<App />, document.getElementById('root')); 