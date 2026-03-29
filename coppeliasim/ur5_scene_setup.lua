--[[
  UR5 CoppeliaSim Scene Setup Script
  Configura los joints para control por posición vía ZMQ Remote API
  sin oscilación ni comportamiento errático.

  INSTRUCCIONES:
  1. Abre CoppeliaSim
  2. Arrastra UR5 desde Model Browser → robots/non-mobile
  3. Haz clic en el UR5 base en la jerarquía
  4. Doble clic en el ícono de script (página)
  5. Reemplaza el contenido con este código
  6. Guarda la escena como "ur5_mqtt_control.ttt"
--]]

function sysCall_init()
    joints = {}

    -- Intentar nombres estándar
    local paths = {
        '/UR5/joint', '/UR5/link2/joint', '/UR5/link3/joint',
        '/UR5/link4/joint', '/UR5/link5/joint', '/UR5/link6/joint'
    }
    local ok = true
    for i = 1, 6 do
        local s, h = pcall(sim.getObject, paths[i])
        if s then joints[i] = h else ok = false; break end
    end

    -- Intentar nombres alternativos
    if not ok then
        joints = {}
        local alt = { '/UR5_joint1','/UR5_joint2','/UR5_joint3',
                      '/UR5_joint4','/UR5_joint5','/UR5_joint6' }
        ok = true
        for i = 1, 6 do
            local s, h = pcall(sim.getObject, alt[i])
            if s then joints[i] = h else ok = false; break end
        end
    end

    -- Búsqueda recursiva si los nombres no coinciden
    if not ok then
        joints = {}
        local found = {}
        local function scan(h, depth)
            if depth > 10 then return end
            local idx = 0
            while true do
                local s, child = pcall(sim.getObjectChild, h, idx)
                if not s or child == -1 then break end
                if sim.getObjectType(child) == sim.sceneobject_joint then
                    table.insert(found, child)
                end
                scan(child, depth + 1)
                idx = idx + 1
            end
        end
        local base = sim.getObject('.')
        scan(base, 0)
        if #found >= 6 then
            for i = 1, 6 do joints[i] = found[i] end
            ok = true
        end
    end

    if #joints < 6 then
        print('[UR5] ⚠️  Solo encontré ' .. #joints .. ' joints. Revisa la escena.')
        return
    end

    -- Configurar cada joint para control de posición estable
    for i = 1, 6 do
        local h = joints[i]
        local alias = sim.getObjectAlias(h, 1)

        -- Modo: control de posición (motor habilitado)
        pcall(sim.setObjectInt32Param, h,
              sim.jointintparam_dynctrlmode, sim.jointdynctrl_position)

        -- Velocidad máxima alta para respuesta rápida sin lag
        pcall(sim.setJointMaxVelocity, h, math.rad(180))   -- 180 deg/s

        -- Fuerza del motor alta para que pueda mantener posición contra gravedad
        pcall(sim.setJointMaxForce, h, 500)

        print('[UR5] J' .. i .. ' = ' .. alias .. ' ✓')
    end

    print('[UR5] Control mode: POSITION | Vel: 180 deg/s | Force: 500 N')
    print('[UR5] Ready for ZMQ Remote API on port 23000')
end

function sysCall_actuation()
    -- Los joints son controlados externamente por el bridge Python via ZMQ
end

function sysCall_sensing()
end

function sysCall_cleanup()
    print('[UR5] Script cleanup')
end
