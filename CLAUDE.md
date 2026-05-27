# CLAUDE.md - ROS 2 LiDAR Web Streamer Project Guide

## 🏗️ System Architecture
This project streams high-bandwidth ROS 2 LiDAR data (PointCloud2 / LaserScan) to a web frontend.
* **Backend:** ROS 2 (Humble/Jazzy) Node written in C++ (for raw performance) or Python.
* **Streaming Protocol:** WebSockets (via `rosbridge_suite`) or WebRTC (for low latency).
* **Frontend:** Next.js (React) + TypeScript.
* **3D Rendering:** Three.js / React Three Fiber (R3F) using WebGL or WebGPU.

## 🛠️ Build & Development Commands
Always use these exact commands to build, run, and test the workspace.

### Backend (ROS 2 / C++)
* **Build Workspace:** `colcon build --symlink-install`
* **Build Single Package:** `colcon build --packages-select <package_name> --symlink-install`
* **Source Environment:** `source install/setup.bash`
* **Run Node:** `ros2 run <package_name> <node_name>`
* **Launch System:** `ros2 launch <launch_package> <launch_file>.launch.py`
* **Test:** `colcon test --packages-select <package_name>`

### Frontend (Next.js)
* **Install Deps:** `npm install` (Do NOT use yarn or pnpm unless specified)
* **Dev Server:** `npm run dev`
* **Production Build:** `npm run build`
* **Linting:** `npm run lint`

## 🎨 Code Style & Standards

### Python (ROS 2 Nodes / Scripts)
* **Style:** Follow PEP 8 and the ROS 2 Python Style Guide.
* **Naming:** `snake_case` for functions/variables, `PascalCase` for classes.
* **Typing:** Always use Python type hints for function arguments and return types.

### C++ (Performance Backend)
* **Style:** ROS 2 C++ Style Guide (modified Google style).
* **Naming:** `camelCase` for variables, `snake_case_` for private class members, `PascalCase` for classes.
* **Memory:** Never use raw `new`/`delete`. Use `std::shared_ptr` and `std::make_shared`.

### TypeScript / Next.js
* **Style:** Functional React components, strict TypeScript typing (avoid `any`).
* **Naming:** `PascalCase` for components, `camelCase` for hooks/utilities/variables.
* **State:** Use localized state or lightweight stores (e.g., Zustand) to prevent unnecessary 3D canvas re-renders.

## ⚠️ Common Pitfalls & High-Effort Guardrails
* **Point Cloud Downsampling:** Raw `sensor_msgs/msg/PointCloud2` data is too heavy for standard WebSockets. Always voxel-grid downsample or convert to a compressed/custom lightweight format on the backend before streaming.
* **Coordinate Frames:** Remember that ROS uses NWU (X-Forwarded, Y-Left, Z-Up), whereas Three.js uses right-handed Y-Up. Always apply coordinate transformations on the frontend.
* **Memory Leaks:** Properly dispose of Three.js geometries and materials when components unmount to avoid crashing the browser tab.

