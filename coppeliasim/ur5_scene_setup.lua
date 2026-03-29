--[[
  UR5 CoppeliaSim Scene Setup
  Control por posición vía ZMQ Remote API (Python bridge)

  INSTRUCCIONES:
  1. Arrastra UR5 desde Model Browser → robots/non-mobile
  2. Clic en UR5 base → doble clic en ícono script (página)
  3. Reemplaza el contenido con este código
  4. Guarda la escena
--]]

function sysCall_init()
    joints = {}

    -- Buscar joints por nombres estándar
    local names = {
        '/UR5/joint', '/UR5/link/joint', '/UR5/link/joint/link/joint',
        '/UR5/link/joint/link/joint/link/joint',
        '/UR5/link/joint/link/joint/link/joint/link/joint',
        '/UR5/joint/link/joint/link/joint/link/joint/link/joint/link/joint'
    }
    local ok = true
    for i = 1, 6 do
        local s, h = pcall(sim.getObject, names[i])
        if s then joints[i] = h else ok = false; break end
    end

    -- Nombres alternativos
    if not ok then
        joints = {}
        local alt = {'/UR5_joint1','/UR5_joint2','/UR5_joint3',
                     '/UR5_joint4','/UR5_joint5','/UR5_joint6'}
        ok = true
        for i = 1, 6 do
            local s, h = pcall(sim.getObject, alt[i])
            if s then joints[i] = h else ok = false; break end
        end
    end

    -- Búsqueda recursiva
    if not ok then
        joints = {}
        local found = {}
        local function scan(h, d)
            if d > 10 then return end
            local i = 0
            while true do
                local s, c = pcall(sim.getObjectChild, h, i)
                if not s or c == -1 then break end
                if sim.getObjectType(c) == sim.sceneobject_joint then
                    table.insert(found, c)
                end
                scan(c, d+1); i = i+1
            end
        end
        scan(sim.getObject('.'), 0)
        if #found >= 6 then
            for i = 1, 6 do joints[i] = found[i] end
            ok = true
        end
    end

    if #joints < 6 then
        print('[UR5] ⚠️ Solo ' .. #joints .. ' joints encontrados')
        return
    end

    -- Configurar joints para control de posición
    for i = 1, 6 do
        local h = joints[i]
        -- Modo posición (PID interno de CoppeliaSim)
        pcall(sim.setObjectInt32Param, h,
              sim.jointintparam_dynctrlmode, sim.jointdynctrl_position)
        -- Velocidad máxima alta → responde rápido sin lag
        pcall(sim.setJointMaxVelocity, h, math.rad(360))  -- 360 deg/s
        -- Fuerza suficiente para sostener contra la gravedad
        pcall(sim.setJointMaxForce, h, 500)
        print('[UR5] J' .. i .. ' = ' .. sim.getObjectAlias(h, 1))
    end

    print('[UR5] Joint control mode: POSITION (PID)')
    print('[UR5] Ready for ZMQ Remote API commands on port 23000')
end

function sysCall_actuation()
    -- Control externo via Python bridge / ZMQ
end

function sysCall_sensing() end
function sysCall_cleanup()
    print('[UR5] Cleanup')
end
