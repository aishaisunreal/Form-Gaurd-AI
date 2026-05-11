# Form Gaurd AI

A real-time workout form analysis that processes body pose landmarks via WebSocket, counts reps, detects form errors, and provides directional correction arrows for live feedback.

---

## Features

- **Real-time form feedback** — analyzes body angles frame-by-frame and flags errors instantly
- **Rep counting** — automatically detects contraction/relaxation phases and counts completed reps
- **Directional correction arrows** — returns vector instructions telling the client where to move a joint
- **Session summary** — on disconnect, sends rep count, average speed, and most common form error
- **5 supported exercises** — Bicep Curls, Push-ups, Lateral Raises, Overhead Press, Overhead Tricep Extension

---

## Supported Exercises

| Key | Exercise |
|---|---|
| `bicepCurls` | Bicep Curls |
| `pushups` | Push-ups |
| `lateralRaises` | Lateral Raises |
| `overheadPress` | Overhead Press |
| `overheadTricepExtension` | Overhead Tricep Extension |

---

## Architecture

```
Flutter Client (camera + pose estimation)
        │
        │  WebSocket (JSON landmarks)
        ▼
 Python WebSocket Server
        │
        ├── get_points()         → parse 33 MediaPipe landmarks
        ├── calculate_angle()    → joint angle from 3 points
        ├── check_<exercise>()   → validate angles, generate arrows
        ├── get_rep_stage()      → detect contraction / relaxation
        └── generate_summary()   → session stats on disconnect
```

The server expects pose landmarks in [MediaPipe Pose](https://ai.google.dev/edge/mediapipe/solutions/vision/pose_landmarker) format (33 keypoints).

---

## Getting Started

### Requirements

- Python 3.10+
- `websockets`
- `numpy`

### Installation

```bash
pip install websockets numpy
```

### Run the server

```bash
python server.py
```

The server starts on `ws://0.0.0.0:81` by default.

---

## WebSocket Protocol

### Client → Server (each frame)

```json
{
  "workout": "bicepCurls",
  "points": [
    { "x": 0.51, "y": 0.23, "z": -0.04 },
    ...
  ]
}
```

`points` must be an array of 33 landmark objects (MediaPipe order), each with `x`, `y`, `z` normalized coordinates.

### Server → Client (each frame)

```json
{
  "message": "Good form",
  "errors": [],
  "reps": 5,
  "arrows": [
    {
      "point": [0.45, 0.62],
      "direction": [0.0, -1.0],
      "joint": "left_elbow"
    }
  ]
}
```

- `message` — short feedback string (first error, or `"Good form"`)
- `errors` — full list of form errors detected this frame
- `reps` — total completed reps in the session
- `arrows` — list of correction vectors to overlay on the camera feed

### Server → Client (on disconnect)

```json
{
  "type": "summary",
  "reps": 12,
  "avg_speed": "18.3 reps/min",
  "most_common_error": "left shoulder: close your shoulders"
}
```

---

## Angle Ranges by Exercise

### Bicep Curls
| Joint | Range |
|---|---|
| Elbow | 40° – 170° |
| Shoulder | 0° – 40° |

### Push-ups
| Joint | Range |
|---|---|
| Elbow | 40° – 150° |
| Shoulder | 30° – 60° |
| Hip | 150° – 180° |
| Knee | 160° – 180° |
| Ankle | 50° – 110° |

### Lateral Raises
| Joint | Range (down) | Range (up) |
|---|---|---|
| Shoulder | 0° – 30° | 70° – 110° |
| Elbow | 150° – 180° | 150° – 180° |

### Overhead Press
| Joint | Range |
|---|---|
| Elbow | 80° – 180° |
| Shoulder | 70° – 180° |

### Overhead Tricep Extension
| Joint | Range |
|---|---|
| Elbow | 50° – 170° |
| Shoulder | 110° – 170° |

---

## Project Structure

```
server.py          # Main file — everything lives here
├── session()                        # Initialize per-connection session state
├── get_points()                     # Parse landmark list into named dict
├── calculate_angle()                # 3-point angle via dot product
├── get_arrow()                      # Perpendicular correction vector
├── get_rep_stage()                  # Contraction/relaxation phase detector
├── check_pushup()                   # Push-up form validator
├── check_bicep_curl()               # Bicep curl form validator
├── check_lateral_raise()            # Lateral raise form validator
├── check_overhead_press()           # Overhead press form validator
├── check_overhead_tricep_extension()# Tricep extension form validator
├── allWorkouts()                    # Dispatcher — routes to correct checker
├── generate_summary()               # End-of-session stats
├── handle_client()                  # WebSocket connection handler
└── main()                           # Server entry point
```

---

## Configuration

| Parameter | Default | Location |
|---|---|---|
| Host | `0.0.0.0` | `main()` |
| Port | `81` | `main()` |
| Default workout | `bicepCurls` | `handle_client()` |

---

made and maintained by aishaisunreal & other team members
