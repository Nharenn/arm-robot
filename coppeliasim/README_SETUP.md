# CoppeliaSim UR5 Scene Setup

## Quick Setup (5 minutes)

### 1. Open CoppeliaSim
Launch CoppeliaSim (V4.6+ recommended).

### 2. Add the UR5 Robot
- Go to the **Model Browser** panel (left side)
- Navigate to: `robots → non-mobile → UR5.ttm`
- Drag it into the scene

### 3. Enable ZMQ Remote API
The ZMQ Remote API should be enabled by default in CoppeliaSim V4.6+.
- Check: `Tools → User Settings → Remote API → ZMQ`
- Default port: **23000**

If not available, add the ZMQ Remote API add-on:
- Copy `simRemoteApi.lua` to CoppeliaSim's add-ons folder

### 4. Configure the UR5 Script
- In the **Scene Hierarchy**, click on the UR5 base object
- Double-click the **script icon** (📄) next to it
- Replace the content with the code from `ur5_scene_setup.lua`
- Press **Ctrl+S** to save

### 5. Save the Scene
- `File → Save Scene As → ur5_mqtt_control.ttt`

### 6. Start Simulation
- Click the **Play** button (▶) or press **Ctrl+Shift+P**
- You should see in the console:
  ```
  [UR5] ✅ All 6 joints found and ready for control
  [UR5] Joint control mode: POSITION (PID)
  [UR5] Ready for ZMQ Remote API commands
  ```

### 7. Run the Python Bridge
```bash
cd backend
python mqtt_bridge.py
```

## Optional: Live Video Streaming

To enable the live video stream in the web interface:

1. In CoppeliaSim, add a **Vision Sensor**:
   - `Add → Vision Sensor → Perspective`
   - Rename it to **ViewSensor** (important: exact name)
   - Position it to have a good view of the robot

2. Run the video stream server:
   ```bash
   python backend/video_stream.py
   ```

3. The stream will be available at `http://localhost:8081`

## Troubleshooting

**"Joint not found" errors:**
- Make sure the UR5 is the standard model from the model browser
- Check the scene hierarchy for the exact joint path names

**"Cannot connect to CoppeliaSim":**
- Make sure the simulation is running (Play button)
- Check that port 23000 is not in use: `lsof -i :23000`
- Try restarting CoppeliaSim

**Joints not moving:**
- Verify joints are in "position control" mode (the Lua script sets this)
- Check that the simulation is not paused
