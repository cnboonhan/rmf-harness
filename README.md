# rmf-harness

Ideas and exploration on implementing a hardness using RMF API and tools, for multi-level building logistics tasks.

## Setup

```
git clone --recurse-submodules https://github.com/cnboonhan/rmf-harness
```

### RMF
```
sudo apt install sqlite3 -y

# Build RMF and rmf-web from source
https://github.com/open-rmf/rmf#building-from-source
https://github.com/open-rmf/rmf-web#getting-started-from-source

Run rmf-web:
source /opt/ros/kilted/setup.bash
source ~/rmf_ws/install/setup.bash

export RMF_API_SERVER_CONFIG=$(git rev-parse --show-toplevel)/api_server_config.py 
cd rmf-web/packages/api-server; pnpm start

Run RMF:
source /opt/ros/kilted/setup.bash
source ~/rmf_ws/install/setup.bash
ros2 launch rmf_demos_gz hotel.launch.xml server_uri:="http://localhost:8000/_internal"

