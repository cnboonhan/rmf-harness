# rmf-harness

Ideas and exploration on implementing a hardness using RMF API and tools, for multi-level building logistics tasks.

## Setup

### RMF
```
# Build RMF and rmf-web from source
https://github.com/open-rmf/rmf#building-from-source
https://github.com/open-rmf/rmf-web#getting-started-from-source

Run it:
# For remote device, forward the web api ports: ssh -L 3390:127.0.0.1:3390 -L 8000:127.0.0.1:8000 -L 5173:127.0.0.1:5173 ubuntu-desktop 
cd rmf-web/packages/api-server; pnpm start
cd rmf-web/packages/rmf-dashboard-framework; pnpm start:example examples/demo
ros2 launch rmf_demos_gz hotel.launch.xml server_uri:="http://localhost:8000/_internal"
