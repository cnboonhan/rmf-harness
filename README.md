# rmf-harness

Ideas and exploration on implementing a hardness using RMF API and tools, for multi-level building logistics tasks.

## Setup

### Pre-requisites
```
git clone --recurse-submodules https://github.com/cnboonhan/rmf-harness
uv sync
```

### Build RMF and rmf-web from source
```
https://github.com/open-rmf/rmf#building-from-source
https://github.com/open-rmf/rmf-web#getting-started-from-source
```

### Run api-server
```
source /opt/ros/kilted/setup.bash; source ~/rmf_ws/install/setup.bash
cd rmf-web/packages/api-server; pnpm start
```

### Run rmf-web
```
source /opt/ros/kilted/setup.bash; source ~/rmf_ws/install/setup.bash
cd rmf-web/packages/rmf-dashboard-framework
pnpm start:example examples/demo
```

### Run RMF Demo (Hotel)
```
source /opt/ros/kilted/setup.bash; source ~/rmf_ws/install/setup.bash
ros2 launch rmf_demos_gz hotel.launch.xml server_uri:="http://localhost:8000/_internal"
```

### Set up cliproxyapi
```
curl -fsSL https://raw.githubusercontent.com/brokechubb/cliproxyapi-installer/refs/heads/master/cliproxyapi-installer | bash
cd ~/cliproxyapi
./cli-proxy-api --claude-login
./cli-proxy-api
curl http://127.0.0.1:8317/v1/models -H "Authorization: Bearer your-api-key-3" 
```

### Run harness
```
uv run harness.py
```
