--[[
╔══════════════════════════════════════════════════════════════╗
║  UR5 CoppeliaSim Scene Setup Script                          ║
║                                                              ║
║  INSTRUCTIONS:                                               ║
║  1. Open CoppeliaSim                                         ║
║  2. Drag UR5 from Model Browser → robots/non-mobile          ║
║  3. Click on the UR5 base in the scene hierarchy             ║
║  4. Double-click the child script icon (page icon)           ║
║  5. Replace the script content with this code                ║
║  6. Save the scene as "ur5_mqtt_control.ttt"                 ║
║                                                              ║
║  This script configures joints for external control via      ║
║  the ZMQ Remote API. The Python bridge controls the joints.  ║
╚══════════════════════════════════════════════════════════════╝
--]]

function sysCall_init()
    joints = {}

    -- ══════════════════════════════════════════
    -- Strategy 1: Try standard path naming
    -- ══════════════════════════════════════════
    local standardPaths = {
        '/UR5/joint',
        '/UR5/link2/joint',
        '/UR5/link3/joint',
        '/UR5/link4/joint',
        '/UR5/link5/joint',
        '/UR5/link6/joint'
    }

    local success = true
    for i = 1, 6 do
        local ok, handle = pcall(sim.getObject, standardPaths[i])
        if ok then
            joints[i] = handle
        else
            success = false
            break
        end
    end

    -- ══════════════════════════════════════════
    -- Strategy 2: Try numbered joint naming
    -- ══════════════════════════════════════════
    if not success then
        joints = {}
        local numberedPaths = {
            '/UR5_joint1', '/UR5_joint2', '/UR5_joint3',
            '/UR5_joint4', '/UR5_joint5', '/UR5_joint6'
        }
        success = true
        for i = 1, 6 do
            local ok, handle = pcall(sim.getObject, numberedPaths[i])
            if ok then
                joints[i] = handle
            else
                success = false
                break
            end
        end
    end

    -- ══════════════════════════════════════════
    -- Strategy 3: Try relative paths from self
    -- ══════════════════════════════════════════
    if not success then
        joints = {}
        local selfHandle = sim.getObject('.')  -- this script's object
        print('[UR5] Self handle: ' .. selfHandle)
        print('[UR5] Self alias: ' .. sim.getObjectAlias(selfHandle, 1))

        -- Try to get the parent (UR5 base)
        local baseHandle = selfHandle
        local ok, parent = pcall(sim.getObjectParent, selfHandle)
        if ok and parent ~= -1 then
            baseHandle = parent
            print('[UR5] Parent alias: ' .. sim.getObjectAlias(baseHandle, 1))
        end

        -- Search all children recursively for joints
        local allJoints = {}
        local function findJoints(handle, depth)
            if depth > 10 then return end
            local idx = 0
            while true do
                local ok2, child = pcall(sim.getObjectChild, handle, idx)
                if not ok2 or child == -1 then break end
                
                local objType = sim.getObjectType(child)
                if objType == sim.sceneobject_joint then
                    table.insert(allJoints, child)
                    local alias = sim.getObjectAlias(child, 1)
                    print('[UR5]   Found joint: ' .. alias .. ' (handle=' .. child .. ')')
                end
                findJoints(child, depth + 1)
                idx = idx + 1
            end
        end

        findJoints(baseHandle, 0)

        if #allJoints >= 6 then
            for i = 1, 6 do
                joints[i] = allJoints[i]
            end
            success = true
            print('[UR5] Found joints by recursive search')
        end
    end

    -- ══════════════════════════════════════════
    -- Strategy 4: Search ALL scene objects for joints
    -- ══════════════════════════════════════════
    if not success then
        joints = {}
        print('[UR5] Searching entire scene for joints...')
        
        local allJoints = {}
        local idx = 0
        while true do
            local ok3, handle = pcall(sim.getObjects, idx, sim.sceneobject_joint)
            if not ok3 or handle == -1 then break end
            
            local alias = sim.getObjectAlias(handle, 1)
            -- Look for joints that belong to UR5
            local aliasLower = string.lower(alias)
            if string.find(aliasLower, 'ur5') or string.find(aliasLower, 'ur3') or 
               string.find(aliasLower, 'joint') then
                table.insert(allJoints, {handle=handle, alias=alias})
                print('[UR5]   Scene joint: ' .. alias .. ' (handle=' .. handle .. ')')
            end
            idx = idx + 1
        end

        -- Try using all found joints if we have at least 6
        if #allJoints >= 6 then
            -- Sort by alias name to ensure consistent ordering
            table.sort(allJoints, function(a, b) return a.alias < b.alias end)
            for i = 1, 6 do
                joints[i] = allJoints[i].handle
            end
            success = true
            print('[UR5] Found ' .. #allJoints .. ' joints by scene scan, using first 6')
        end
    end

    -- ══════════════════════════════════════════
    -- Strategy 5: Get ALL joints in scene regardless of name
    -- ══════════════════════════════════════════
    if not success then
        joints = {}
        print('[UR5] Last resort: getting all joints in scene...')
        
        local allJoints = {}
        local idx = 0
        while true do
            local ok4, handle = pcall(sim.getObjects, idx, sim.sceneobject_joint)
            if not ok4 or handle == -1 then break end
            
            local alias = sim.getObjectAlias(handle, 1)
            table.insert(allJoints, {handle=handle, alias=alias})
            print('[UR5]   ALL joint: ' .. alias .. ' (handle=' .. handle .. ')')
            idx = idx + 1
        end

        if #allJoints >= 6 then
            table.sort(allJoints, function(a, b) return a.alias < b.alias end)
            for i = 1, math.min(6, #allJoints) do
                joints[i] = allJoints[i].handle
            end
            success = true
        end
    end

    -- ══════════════════════════════════════════
    -- Configure joints
    -- ══════════════════════════════════════════
    if #joints >= 6 then
        print('[UR5] ✅ Found ' .. #joints .. ' joints — configuring for position control')

        for i = 1, 6 do
            -- Set to position control mode (for PID control)
            pcall(sim.setObjectInt32Param, joints[i], 
                  sim.jointintparam_dynctrlmode, sim.jointdynctrl_position)
            
            local alias = sim.getObjectAlias(joints[i], 1)
            print('[UR5]   J' .. i .. ' = ' .. alias .. ' (handle=' .. joints[i] .. ')')
        end

        print('[UR5] Joint control mode: POSITION (PID)')
        print('[UR5] Ready for ZMQ Remote API commands on port 23000')
    else
        print('[UR5] ⚠️  Found ' .. #joints .. ' joints (expected 6)')
        print('[UR5] Please check the scene hierarchy for UR5 joint objects')
        print('[UR5] The robot model must contain at least 6 revolute joints')
    end
end

function sysCall_actuation()
    -- Joint control is handled externally via the Python bridge
    -- through the ZMQ Remote API (sim.setJointTargetPosition)
end

function sysCall_sensing()
    -- Optional: read sensor data
end

function sysCall_cleanup()
    print('[UR5] Script cleanup complete')
end
