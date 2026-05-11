import numpy as np
import numpy.typing as npt
from enum import Enum
import asyncio
import json
import websockets
import re
import time
from collections import Counter



def session():
    return {
        "reps": 0,
        "previous_rep_stage": RepStage.CONTRACTION,
        "workout": Workout.BICEP_CURLS,
        "error_log": [],
        "rep_timestamps": [],
        "start_time": time.time(),
    }


landmark_names = [
    "nose", "left_eye_inner", "left_eye", "left_eye_outer",
    "right_eye_inner", "right_eye", "right_eye_outer",
    "left_ear", "right_ear", "mouth_left", "mouth_right",
    "left_shoulder", "right_shoulder", "left_elbow", "right_elbow",
    "left_wrist", "right_wrist", "left_pinky", "right_pinky",
    "left_index", "right_index", "left_thumb", "right_thumb",
    "left_hip", "right_hip", "left_knee", "right_knee",
    "left_ankle", "right_ankle", "left_heel", "right_heel",
    "left_foot_index", "right_foot_index"
]


def get_points(landmarks):
    point = {}
    for i, n in enumerate(landmark_names):
        lm = landmarks[i]
        point[n] = [lm["x"], lm["y"], lm["z"]]

    return point


def calculate_angle(a: list[float], b: list[float], c: list[float]) -> float:
    a = np.array(a)
    b = np.array(b)
    c = np.array(c)

    ba = a - b
    bc = c - b

    cosine_angle = np.dot(ba, bc) / (np.linalg.norm(ba) * np.linalg.norm(bc) + 1e-6)
    cosine_angle = np.clip(cosine_angle, -1.0, 1.0)

    angle = np.degrees(np.arccos(cosine_angle))
    return angle


def get_arrow(a: list[float], b: list[float], rotate_clockwise: bool) -> npt.NDArray[np.float64]:
    vec_x = b[0] - a[0]
    vec_y = b[1] - a[1]

    if rotate_clockwise:
        rotated_vec_x, rotated_vec_y = vec_y, -vec_x
    else:
        rotated_vec_x, rotated_vec_y = -vec_y, vec_x

    arrow = np.array([rotated_vec_x, rotated_vec_y])
    arrow = arrow / np.linalg.norm(arrow)
    return arrow


class RepStage(Enum):
    CONTRACTION = 1
    RELAXATION = 2


class Workout(Enum):
    PUSHUPS = 1
    BICEP_CURLS = 2
    LATERAL_RAISES = 3
    OVERHEAD_PRESS = 4
    OVERHEAD_TRICEP_EXTENSION = 5


def generate_summary(reps, error_log, rep_timestamps):
    if len(rep_timestamps) >= 2:
        elapsed = rep_timestamps[-1] - rep_timestamps[0]
        avg_speed = (len(rep_timestamps) - 1) / elapsed * 60
        avg_speed_str = f"{avg_speed:.1f} reps/min"
    else:
        avg_speed_str = "N/A"

    if error_log:
        most_common = Counter(error_log).most_common(1)[0][0]
    else:
        most_common = "None - great form!"

    return {
        "type": "summary",
        "reps": reps,
        "avg_speed": avg_speed_str,
        "most_common_error": most_common,
    }


def get_rep_stage(
    previous_rep_stage: RepStage,
    left_val: float,
    right_val: float,
    relax_threshold: float,
    contract_threshold: float,
    reversed_threshold: bool
) -> RepStage:
    if reversed_threshold:
        if left_val > relax_threshold and right_val > relax_threshold:
            return RepStage.RELAXATION
        elif left_val < contract_threshold and right_val < contract_threshold:
            return RepStage.CONTRACTION
        else:
            return previous_rep_stage
    else:
        if left_val < relax_threshold and right_val < relax_threshold:
            return RepStage.RELAXATION
        elif left_val > contract_threshold and right_val > contract_threshold:
            return RepStage.CONTRACTION
        else:
            return previous_rep_stage


def check_pushup(angles, phase, points, arrows):
    arrow_instructions = []
    ranges = {
        "elbow": (40, 150),
        "shoulder": (30, 60),
        "hip": (150, 180),
        "knee": (160, 180),
        "ankle": (50, 110)
    }
    results = {}
    errors = []

    for side in ["left", "right"]:
        elbow = angles[f"{side}_elbow"]
        shoulder = angles[f"{side}_shoulder"]
        hip = angles[f"{side}_hip"]
        knee = angles[f"{side}_knee"]
        ankle = angles[f"{side}_ankle"]

        elbow_ok = ranges["elbow"][0] <= elbow <= ranges["elbow"][1]
        shoulder_ok = ranges["shoulder"][0] <= shoulder <= ranges["shoulder"][1]
        hip_ok = ranges["hip"][0] <= hip <= ranges["hip"][1]
        knee_ok = ranges["knee"][0] <= knee <= ranges["knee"][1]
        ankle_ok = ranges["ankle"][0] <= ankle <= ranges["ankle"][1]
        results[side] = elbow_ok and shoulder_ok and hip_ok and knee_ok and ankle_ok

        if elbow < ranges["elbow"][0]:
            errors.append(f"{side} elbow: relax more ({int(elbow)}, target: {ranges['elbow'][0]}-{ranges['elbow'][1]})")
            arrow_instructions.append({
                "point": points[f"{side}_wrist"][:2],
                "direction": get_arrow( points[f"{side}_wrist"], arrows[f"{side}_elbow"], True).tolist(),
                "joint": f"{side}_elbow"
            })

        elif elbow > ranges["elbow"][1]:
            errors.append(f"{side} elbow: contract more ({int(elbow)}, target: {ranges['elbow'][0]}-{ranges['elbow'][1]})")
            arrow_instructions.append({
                "point": points[f"{side}_wrist"][:2],
                "direction": get_arrow( points[f"{side}_wrist"], arrows[f"{side}_elbow"], False).tolist(),
                "joint": f"{side}_elbow"
            })

        if shoulder < ranges["shoulder"][0]:
            errors.append(f"{side} shoulder: raise (now: {int(shoulder)}, target: {ranges['shoulder'][0]}-{ranges['shoulder'][1]})")
            arrow_instructions.append({
                "point": points[f"{side}_elbow"][:2],
                "direction": get_arrow( points[f"{side}_elbow"], arrows[f"{side}_shoulder"], True).tolist(),
                "joint": f"{side}_shoulder"
            })

        elif shoulder > ranges["shoulder"][1]:
            errors.append(f"{side} shoulder: lower (now: {int(shoulder)}, target: {ranges['shoulder'][0]}-{ranges['shoulder'][1]})")
            arrow_instructions.append({
                "point": points[f"{side}_elbow"][:2],
                "direction": get_arrow( points[f"{side}_elbow"], arrows[f"{side}_shoulder"], False).tolist(),
                "joint": f"{side}_shoulder"
            })

        if hip < ranges["hip"][0]:
            errors.append(f"{side} hip: lift (now: {int(hip)}, target: {ranges['hip'][0]}-{ranges['hip'][1]})")
            arrow_instructions.append({
                "point": points[f"{side}_hip"][:2],
                "direction": get_arrow( points[f"{side}_hip"], arrows[f"{side}_hip"], True).tolist(),
                "joint": f"{side}_hip"
            })

        elif hip > ranges["hip"][1]:
            errors.append(f"{side} hip: lower (now: {int(hip)}, target: {ranges['hip'][0]}-{ranges['hip'][1]})")
            arrow_instructions.append({
                "point": points[f"{side}_hip"][:2],
                "direction": get_arrow( points[f"{side}_hip"], arrows[f"{side}_hip"], False).tolist(),
                "joint": f"{side}_hip"
            })

        if knee < ranges["knee"][0]:
            errors.append(f"{side} knee: straighten (now: {int(knee)}, target: {ranges['knee'][0]}-{ranges['knee'][1]})")
            arrow_instructions.append({
                "point": points[f"{side}_ankle"][:2],
                "direction": get_arrow( points[f"{side}_ankle"], arrows[f"{side}_knee"], True).tolist(),
                "joint": f"{side}_knee"
            })

        elif knee > ranges["knee"][1]:
            errors.append(f"{side} knee: bend (now: {int(knee)}, target: {ranges['knee'][0]}-{ranges['knee'][1]})")
            arrow_instructions.append({
                "point": points[f"{side}_ankle"][:2],
                "direction": get_arrow( points[f"{side}_ankle"], arrows[f"{side}_knee"], False).tolist(),
                "joint": f"{side}_knee"
            })

        if ankle < ranges["ankle"][0]:
            errors.append(f"{side} ankle: flex more (now: {int(ankle)}, target: {ranges['ankle'][0]}-{ranges['ankle'][1]})")
            arrow_instructions.append({
                "point": points[f"{side}_foot_index"][:2],
                "direction": get_arrow( points[f"{side}_foot_index"], arrows[f"{side}_ankle"], True).tolist(),
                "joint": f"{side}_ankle"
            })

        elif ankle > ranges["ankle"][1]:
            errors.append(f"{side} ankle: relax more (now: {int(ankle)}, target: {ranges['ankle'][0]}-{ranges['ankle'][1]})")
            arrow_instructions.append({
                "point": points[f"{side}_foot_index"][:2],
                "direction": get_arrow( points[f"{side}_foot_index"], arrows[f"{side}_ankle"], False).tolist(),
                "joint": f"{side}_ankle"
            })

    state = len(errors) == 0
    return state, errors, arrow_instructions


def check_bicep_curl(angles, phase,  points, arrows):
    arrow_instructions = []
    ranges = {
        "elbow": (40, 170),
        "shoulder": (0, 40),
        "hip": (160, 180)
    }

    errors = []

    for side in ["left", "right"]:
        elbow = angles[f"{side}_elbow"]
        shoulder = angles[f"{side}_shoulder"]
        hip = angles[f"{side}_hip"]

        if elbow < ranges["elbow"][0]:
            errors.append(f"{side} elbow: relax more ({int(elbow)}, target: {ranges['elbow'][0]}-{ranges['elbow'][1]})")
            arrow_instructions.append({
                "point": points[f"{side}_wrist"][:2],
                "direction": get_arrow( points[f"{side}_wrist"], arrows[f"{side}_elbow"], True).tolist(),
                "joint": f"{side}_elbow"
            })

        elif elbow > ranges["elbow"][1]:
            errors.append(f"{side} elbow: contract more ({int(elbow)}, target: {ranges['elbow'][0]}-{ranges['elbow'][1]})")
            arrow_instructions.append({
                "point": points[f"{side}_wrist"][:2],
                "direction": get_arrow( points[f"{side}_wrist"], arrows[f"{side}_elbow"], False).tolist(),
                "joint": f"{side}_elbow"
            })

        if shoulder > ranges["shoulder"][1]:
            errors.append(f"{side} shoulder: close your shoulders ({int(shoulder)}, target: {ranges['shoulder'][0]}-{ranges['shoulder'][1]})")
            arrow_instructions.append({
                "point": points[f"{side}_elbow"][:2],
                "direction": get_arrow( points[f"{side}_elbow"], arrows[f"{side}_shoulder"], False).tolist(),
                "joint": f"{side}_shoulder"
            })

    state = len(errors) == 0
    return state, errors, arrow_instructions


def check_lateral_raise(angles, phase,  points, arrows):
    arrow_instructions = []
    ranges = {
        "shoulder_down": (0, 30),
        "shoulder_up": (70, 110),
        "elbow": (150, 180),
        "hip": (150, 180)
    }

    results = {}
    errors = []

    for side in ["left", "right"]:
        shoulder = angles[f"{side}_shoulder"]
        elbow = angles[f"{side}_elbow"]
        hip = angles[f"{side}_hip"]

        shoulder_ok = (
            ranges["shoulder_down"][0] <= shoulder <= ranges["shoulder_down"][1]
            or ranges["shoulder_up"][0] <= shoulder <= ranges["shoulder_up"][1]
        )

        elbow_ok = ranges["elbow"][0] <= elbow <= ranges["elbow"][1]
        hip_ok = ranges["hip"][0] <= hip <= ranges["hip"][1]

        results[side] = shoulder_ok and elbow_ok and hip_ok

        if phase == "relaxation":
            if shoulder > ranges["shoulder_down"][1]:
                errors.append(f"{side} arm: lower your arm ({int(shoulder)})")
                arrow_instructions.append({
                    "point": points[f"{side}_elbow"][:2],
                    "direction": get_arrow( points[f"{side}_elbow"], arrows[f"{side}_shoulder"], False).tolist(),
                    "joint": f"{side}_shoulder"
                })

        elif phase == "contraction":
            if shoulder < ranges["shoulder_up"][0]:
                errors.append(f"{side} arm: raise higher ({int(shoulder)})")
                arrow_instructions.append({
                    "point": points[f"{side}_elbow"][:2],
                    "direction": get_arrow( points[f"{side}_elbow"], arrows[f"{side}_shoulder"], True).tolist(),
                    "joint": f"{side}_shoulder"
                })

            elif shoulder > ranges["shoulder_up"][1]:
                errors.append(f"{side} arm: too high ({int(shoulder)})")
                arrow_instructions.append({
                    "point": points[f"{side}_elbow"][:2],
                    "direction": get_arrow( points[f"{side}_elbow"], arrows[f"{side}_shoulder"], False).tolist(),
                    "joint": f"{side}_shoulder"
                })

        if elbow < ranges["elbow"][0]:
            errors.append(f"{side} elbow: don't bend too much ({int(elbow)})")
            arrow_instructions.append({
                "point": points[f"{side}_wrist"][:2],
                "direction": get_arrow( points[f"{side}_wrist"], arrows[f"{side}_elbow"], True).tolist(),
                "joint": f"{side}_elbow"
            })

    state = len(errors) == 0
    return state, errors, arrow_instructions


def check_overhead_press(angles, phase,  points, arrows):
    arrow_instructions = []
    ranges = {
        "elbow": (80, 180),
        "shoulder": (70, 180),
        "hip": (160, 180)
    }

    errors = []

    for side in ["left", "right"]:
        elbow = angles[f"{side}_elbow"]
        shoulder = angles[f"{side}_shoulder"]
        hip = angles[f"{side}_hip"]

        if elbow < ranges["elbow"][0]:
            errors.append(f"{side} elbow:  push your arms higher above your head({int(elbow)}°, target: {ranges['elbow'][0]}-{ranges['elbow'][1]})")
            arrow_instructions.append({
                "point": points[f"{side}_wrist"][:2],
                "direction": get_arrow( points[f"{side}_wrist"], arrows[f"{side}_elbow"], True).tolist(),
                "joint": f"{side}_elbow"
            })

        elif elbow > ranges["elbow"][1]:
            errors.append(f"{side} elbow: don’t push too hard at the top ({int(elbow)}°, target: {ranges['elbow'][0]}-{ranges['elbow'][1]})")
            arrow_instructions.append({
                "point": points[f"{side}_wrist"][:2],
                "direction": get_arrow( points[f"{side}_wrist"], arrows[f"{side}_elbow"], False).tolist(),
                "joint": f"{side}_elbow"
            })

        if shoulder < ranges["shoulder"][0]:
            errors.append(f"{side} shoulder:lift the weight higher ({int(shoulder)}°, target: {ranges['shoulder'][0]}-{ranges['shoulder'][1]})")
            arrow_instructions.append({
                "point": points[f"{side}_elbow"][:2],
                "direction": get_arrow( points[f"{side}_elbow"], arrows[f"{side}_shoulder"], True).tolist(),
                "joint": f"{side}_shoulder"
            })

        elif shoulder > ranges["shoulder"][1]:
            errors.append(f"{side} shoulder:bring the weight down slowly ({int(shoulder)}°, target: {ranges['shoulder'][0]}-{ranges['shoulder'][1]})")
            arrow_instructions.append({
                "point": points[f"{side}_elbow"][:2],
                "direction": get_arrow( points[f"{side}_elbow"], arrows[f"{side}_shoulder"], False).tolist(),
                "joint": f"{side}_shoulder"
            })

    state = len(errors) == 0
    return state, errors, arrow_instructions


def check_overhead_tricep_extension(angles, phase,  points, arrows):
    arrow_instructions = []
    ranges = {
        "elbow": (50, 170),
        "shoulder": (110, 170),
        "hip": (150, 180)
    }

    errors = []

    for side in ["left", "right"]:
        elbow = angles[f"{side}_elbow"]
        shoulder = angles[f"{side}_shoulder"]
        hip = angles[f"{side}_hip"]

        if elbow < ranges["elbow"][0]:
            errors.append(f"{side} elbow: relax more ({int(elbow)}, target: {ranges['elbow'][0]}-{ranges['elbow'][1]})")
            arrow_instructions.append({
                "point": points[f"{side}_wrist"][:2],
                "direction": get_arrow( points[f"{side}_wrist"], arrows[f"{side}_elbow"], True).tolist(),
                "joint": f"{side}_elbow"
            })

        elif elbow > ranges["elbow"][1]:
            errors.append(f"{side} elbow: contract more ({int(elbow)}, target: {ranges['elbow'][0]}-{ranges['elbow'][1]})")
            arrow_instructions.append({
                "point": points[f"{side}_wrist"][:2],
                "direction": get_arrow( points[f"{side}_wrist"], arrows[f"{side}_elbow"], False).tolist(),
                "joint": f"{side}_elbow"
            })

        if shoulder < ranges["shoulder"][0]:
            errors.append(f"{side} shoulder: open your shoulders ({int(shoulder)}, target: {ranges['shoulder'][0]}-{ranges['shoulder'][1]})")
            arrow_instructions.append({
                "point": points[f"{side}_elbow"][:2],
                "direction": get_arrow( points[f"{side}_elbow"], arrows[f"{side}_shoulder"], True).tolist(),
                "joint": f"{side}_shoulder"
            })

        elif shoulder > ranges["shoulder"][1]:
            errors.append(f"{side} shoulder: close your shoulders ({int(shoulder)}, target: {ranges['shoulder'][0]}-{ranges['shoulder'][1]})")
            arrow_instructions.append({
                "point": points[f"{side}_elbow"][:2],
                "direction": get_arrow( points[f"{side}_elbow"], arrows[f"{side}_shoulder"], False).tolist(),
                "joint": f"{side}_shoulder"
            })

    state = len(errors) == 0
    return state, errors, arrow_instructions


check_func = {
    Workout.PUSHUPS: check_pushup,
    Workout.BICEP_CURLS: check_bicep_curl,
    Workout.LATERAL_RAISES: check_lateral_raise,
    Workout.OVERHEAD_PRESS: check_overhead_press,
    Workout.OVERHEAD_TRICEP_EXTENSION: check_overhead_tricep_extension,
}


def allWorkouts(sess, normal_points):
    error_log = sess["error_log"]
    rep_timestamps = sess["rep_timestamps"]
    selected_workout = sess["workout"]
    reps = sess["reps"]
    previous_rep_stage = sess["previous_rep_stage"]

    angles = {}

    if selected_workout == Workout.PUSHUPS:
        angles = {
            "left_elbow": calculate_angle(normal_points["left_shoulder"], normal_points["left_elbow"], normal_points["left_wrist"]),
            "right_elbow": calculate_angle(normal_points["right_shoulder"], normal_points["right_elbow"], normal_points["right_wrist"]),
            "left_shoulder": calculate_angle(normal_points["left_hip"], normal_points["left_shoulder"], normal_points["left_elbow"]),
            "right_shoulder": calculate_angle(normal_points["right_hip"], normal_points["right_shoulder"], normal_points["right_elbow"]),
            "left_hip": calculate_angle(normal_points["left_shoulder"], normal_points["left_hip"], normal_points["left_knee"]),
            "right_hip": calculate_angle(normal_points["right_shoulder"], normal_points["right_hip"], normal_points["right_knee"]),
            "left_knee": calculate_angle(normal_points["left_hip"], normal_points["left_knee"], normal_points["left_ankle"]),
            "right_knee": calculate_angle(normal_points["right_hip"], normal_points["right_knee"], normal_points["right_ankle"]),
            "left_ankle": calculate_angle(normal_points["left_knee"], normal_points["left_ankle"], normal_points["left_foot_index"]),
            "right_ankle": calculate_angle(normal_points["right_knee"], normal_points["right_ankle"], normal_points["right_foot_index"])
        }

    elif selected_workout in (
        Workout.BICEP_CURLS,
        Workout.LATERAL_RAISES,
        Workout.OVERHEAD_TRICEP_EXTENSION,
        Workout.OVERHEAD_PRESS
    ):
        angles = {
            "left_elbow": calculate_angle(normal_points["left_shoulder"], normal_points["left_elbow"], normal_points["left_wrist"]),
            "right_elbow": calculate_angle(normal_points["right_shoulder"], normal_points["right_elbow"], normal_points["right_wrist"]),
            "left_shoulder": calculate_angle(normal_points["left_hip"], normal_points["left_shoulder"], normal_points["left_elbow"]),
            "right_shoulder": calculate_angle(normal_points["right_hip"], normal_points["right_shoulder"], normal_points["right_elbow"]),
            "left_hip": calculate_angle(normal_points["left_shoulder"], normal_points["left_hip"], normal_points["left_knee"]),
            "right_hip": calculate_angle(normal_points["right_shoulder"], normal_points["right_hip"], normal_points["right_knee"])
        }

    arrows = {
        "left_elbow": get_arrow(normal_points["left_elbow"], normal_points["left_wrist"], rotate_clockwise=False),
        "right_elbow": get_arrow(normal_points["right_elbow"], normal_points["right_wrist"], rotate_clockwise=True),
        "left_shoulder": get_arrow(normal_points["left_shoulder"], normal_points["left_elbow"], rotate_clockwise=True),
        "right_shoulder": get_arrow(normal_points["right_shoulder"], normal_points["right_elbow"], rotate_clockwise=False),
        "left_hip": get_arrow(normal_points["left_shoulder"], normal_points["left_hip"], rotate_clockwise=True),
        "right_hip": get_arrow(normal_points["right_shoulder"], normal_points["right_hip"], rotate_clockwise=False),
        "left_knee": get_arrow(normal_points["left_knee"], normal_points["left_ankle"], rotate_clockwise=False),
        "right_knee": get_arrow(normal_points["right_knee"], normal_points["right_ankle"], rotate_clockwise=True),
        "left_ankle": get_arrow(normal_points["left_ankle"], normal_points["left_foot_index"], rotate_clockwise=True),
        "right_ankle": get_arrow(normal_points["right_ankle"], normal_points["right_foot_index"], rotate_clockwise=False),
    }

    

    phase = previous_rep_stage.name.lower()

    state, errors, arrow_instructions = check_func[selected_workout](
        angles, phase,  normal_points, arrows
    )
    current_rep_stage = previous_rep_stage
    if not state:
        clean_errors = [re.sub(r'\s*\(.*?\)', '', e).strip() for e in errors]
        error_log.extend(clean_errors)
        current_rep_stage = previous_rep_stage

    if state:
        if selected_workout == Workout.PUSHUPS:
            current_rep_stage = get_rep_stage(previous_rep_stage, angles["left_elbow"], angles["right_elbow"], 80, 110, False)
        elif selected_workout == Workout.BICEP_CURLS:
            current_rep_stage = get_rep_stage(previous_rep_stage, angles["left_elbow"], angles["right_elbow"], 80, 140, False)
        elif selected_workout == Workout.LATERAL_RAISES:
            current_rep_stage = get_rep_stage(previous_rep_stage, angles["left_shoulder"], angles["right_shoulder"], 70, 30, True)
        elif selected_workout == Workout.OVERHEAD_TRICEP_EXTENSION:
            current_rep_stage = get_rep_stage(previous_rep_stage, angles["left_elbow"], angles["right_elbow"], 140, 90, True)
        elif selected_workout == Workout.OVERHEAD_PRESS:
            current_rep_stage = get_rep_stage(previous_rep_stage, angles["left_elbow"], angles["right_elbow"], 110, 150, False)

        if current_rep_stage != previous_rep_stage:
            previous_rep_stage = current_rep_stage
            if previous_rep_stage == RepStage.CONTRACTION:
                reps += 1
                rep_timestamps.append(time.time())

    sess["previous_rep_stage"] = previous_rep_stage
    sess["reps"] = reps

    return {
        "message": "Good form" if state else errors[0],
        "errors": errors,
        "reps": reps,
        "arrows": arrow_instructions,
    }


async def handle_client(websocket):
    print(f"flutter client connected: {websocket.remote_address}")
    sess = session()

    try:
        async for message in websocket:
            data = json.loads(message)

            print(f"landmarks recieved: {data}")
            name = data.get("workout", "bicepCurls")
            workout_map = {
             "bicepCurls": Workout.BICEP_CURLS,
             "pushups": Workout.PUSHUPS,
             "lateralRaises": Workout.LATERAL_RAISES,
             "overheadPress": Workout.OVERHEAD_PRESS,
             "overheadTricepExtension": Workout.OVERHEAD_TRICEP_EXTENSION,}
            sess["workout"] = workout_map.get(name, Workout.BICEP_CURLS)
            landmarks_data = get_points(data["points"])

            error_results = allWorkouts(sess, landmarks_data)

            response = json.dumps(error_results)
            await websocket.send(response)

    except websockets.exceptions.ConnectionClosedError as e:
        print(f"Connection closing failed. error: ..{e}")
    except json.JSONDecodeError as e:
        print(f"invalid JSON received. error: ..{e}")
    finally:
        summary = generate_summary(sess["reps"], sess["error_log"], sess["rep_timestamps"])
        try:
          await websocket.send(json.dumps(summary))
        except:
         pass
        print(f"Connection closed successfully from client: {websocket.remote_address}")


async def main():
    host = "0.0.0.0"
    port = 81
    print(f"Websockets server running on ws://{host}:{port}")

    async with websockets.serve(handle_client, host, port):
        await asyncio.Future()


if __name__ == "__main__":
    asyncio.run(main())