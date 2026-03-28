# Despliegue UR5 Control Station

## Arquitectura de despliegue

```
Profesor (cualquier lugar)          Tu Mac (servidor local)
┌─────────────────────┐           ┌──────────────────────────┐
│  Navegador          │           │  CoppeliaSim (UR5)       │
│  ↓                  │           │  Python Bridge (MQTT↔ZMQ)│
│  Vercel (frontend)  │──Ngrok──→│  Mosquitto (puerto 9001)  │
│                     │──Ngrok──→│  Video Stream (puerto 8081)│
└─────────────────────┘           └──────────────────────────┘
```

## Paso 1: Subir frontend a Vercel

### Opción A: Desde GitHub (recomendado)
1. Sube tu proyecto a un repositorio en GitHub
2. Ve a https://vercel.com y crea cuenta con GitHub
3. Click "Add New Project" → selecciona tu repo
4. Vercel detecta Vite automáticamente → click "Deploy"
5. En ~1 minuto tendrás una URL como `tu-proyecto.vercel.app`

### Opción B: Desde terminal
```bash
npm install -g vercel
cd "Program SImulation"
vercel
# Sigue las instrucciones (acepta defaults)
```

## Paso 2: Preparar tu Mac como servidor

```bash
# 1. Instalar todo (solo la primera vez)
./setup.sh

# 2. Abrir CoppeliaSim → cargar UR5 → Play

# 3. Iniciar todos los servicios
./start.sh
```

## Paso 3: Exponer con Ngrok

```bash
# Solo la primera vez: autenticarse
ngrok config add-authtoken TU_TOKEN_DE_NGROK

# Abrir los túneles
./start_remote.sh
```

Ngrok mostrará las URLs públicas. Ejemplo:
```
Frontend:     https://tu-proyecto.vercel.app     (ya está en la nube)
MQTT WS:      https://abc123.ngrok-free.app      (puerto 9001)
Video Stream: https://xyz789.ngrok-free.app      (puerto 8081)
```

## Paso 4: El profesor se conecta

1. Abre `https://tu-proyecto.vercel.app` en su navegador
2. Aparece el panel "Conectar al Robot"
3. Pega las URLs de Ngrok:
   - MQTT Broker: `wss://abc123.ngrok-free.app`
   - Video Stream: `https://xyz789.ngrok-free.app`
4. Click "Conectar al Robot"

### Link directo (sin configuración manual)
Puedes compartir un link preconfigurado:
```
https://tu-proyecto.vercel.app?mqtt=wss://abc123.ngrok-free.app&stream=https://xyz789.ngrok-free.app
```
El profesor solo abre el link y automáticamente se conecta.

## Notas importantes

- Tu Mac debe estar encendida y con CoppeliaSim corriendo
- Las URLs de Ngrok cambian cada vez que reinicias (plan gratuito)
- Para URLs fijas, usa Ngrok con plan de pago o Tailscale
- El frontend en Vercel es estático, no necesita tu Mac para cargar
